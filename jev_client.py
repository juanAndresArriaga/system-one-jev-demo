"""Minimal System One / Jev client: mock (default) or live TypeSafe API."""

from __future__ import annotations

import os
import re
from typing import Any

import httpx

DEFAULT_URL = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-latest"


def system_one(
    *,
    state: str | dict[str, Any],
    questions: dict[str, Any],
    live: bool = False,
    model: str | None = None,
    api_key: str | None = None,
    api_url: str | None = None,
) -> dict[str, Any]:
    """Evaluate `questions` against `state`.

    Returns a dict shaped like::

        {
          "model": "...",
          "answers": { "<id>": { "type": "noul|choice|score", ... } },
          "usage": { "input_tokens": int, "output_tokens": int },
          "source": "mock" | "live",
        }
    """
    if live:
        return _live(
            state=state,
            questions=questions,
            model=model or os.getenv("TYPESAFE_MODEL", DEFAULT_MODEL),
            api_key=api_key or os.getenv("TYPESAFE_API_KEY"),
            api_url=api_url or os.getenv("TYPESAFE_API_URL", DEFAULT_URL),
        )
    return _mock(state=state, questions=questions)


def _live(
    *,
    state: str | dict[str, Any],
    questions: dict[str, Any],
    model: str,
    api_key: str | None,
    api_url: str,
) -> dict[str, Any]:
    if not api_key:
        raise SystemExit(
            "--live needs TYPESAFE_API_KEY (see .env.example). "
            "Run without --live to use the offline mock."
        )
    payload = {"model": model, "state": state, "questions": questions}
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            api_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
    # Normalize common response shapes (answers vs nested groups).
    answers = data.get("answers") or {}
    if not answers:
        for key in ("nouls", "choices", "scores"):
            group = data.get(key) or {}
            for qid, val in group.items():
                answers[qid] = {"type": key.rstrip("s") if key != "nouls" else "noul", **val}
    return {
        "model": data.get("model", model),
        "answers": answers,
        "usage": data.get("usage") or {},
        "source": "live",
        "raw": data,
    }


def _mock(*, state: str | dict[str, Any], questions: dict[str, Any]) -> dict[str, Any]:
    """Heuristic stand-in so the demo runs without an API key."""
    text = _flatten_state(state).lower()
    answers: dict[str, Any] = {}

    for qid, q in questions.items():
        qtype = q.get("type")
        if qtype == "noul":
            answers[qid] = {"type": "noul", "noul": _noul_prob(text, q)}
        elif qtype == "choice":
            answers[qid] = _choice_answer(text, q)
        elif qtype == "score":
            answers[qid] = _score_answer(text, q)
        else:
            raise ValueError(f"Unknown question type for {qid!r}: {qtype!r}")

    return {
        "model": "mock-system-one",
        "answers": answers,
        "usage": {"input_tokens": max(1, len(text) // 4), "output_tokens": 0},
        "source": "mock",
    }


def _flatten_state(state: str | dict[str, Any]) -> str:
    if isinstance(state, str):
        return state
    parts: list[str] = []

    def walk(obj: Any, prefix: str = "") -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, f"{prefix}.{k}" if prefix else str(k))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f"{prefix}[{i}]")
        else:
            parts.append(f"{prefix}: {obj}")

    walk(state)
    return "\n".join(parts)


def _noul_prob(text: str, q: dict[str, Any]) -> float:
    instructions = (q.get("instructions") or "").lower()
    # Keyword heuristics tied to common triage questions in demo.py
    if "refund" in instructions or "money back" in instructions:
        return _clip(0.15 + 0.75 * _any(text, ["refund", "charged twice", "money back", "double charge"]))
    if "urgent" in instructions or "urgency" in instructions:
        return _clip(0.1 + 0.8 * _any(text, ["asap", "urgent", "immediately", "right now", "blocker"]))
    if "reproduce" in instructions or "repro" in instructions:
        return _clip(0.2 + 0.7 * _any(text, ["steps", "repro", "reproduce", "safari", "chrome"]))
    if "human" in instructions or "agent" in instructions:
        return _clip(0.2 + 0.7 * _any(text, ["lawyer", "lawsuit", "cancel subscription", "manager"]))
    # Generic: lean yes if instruction keywords appear in state
    tokens = [t for t in re.findall(r"[a-z]{4,}", instructions) if t not in {"does", "this", "that", "with", "from"}]
    hits = sum(1 for t in tokens if t in text)
    return _clip(0.25 + 0.15 * hits)


def _choice_answer(text: str, q: dict[str, Any]) -> dict[str, Any]:
    criteria: dict[str, Any] = q.get("criteria") or {}
    labels = list(criteria.keys())
    if not labels:
        raise ValueError("choice questions need criteria")

    scores = {label: 0.05 for label in labels}
    for label, desc in criteria.items():
        blob = f"{label} {desc or ''}".lower()
        keywords = [w for w in re.findall(r"[a-z]{3,}", blob) if w not in {"the", "and", "for", "with"}]
        scores[label] = 0.05 + sum(0.35 for w in keywords if w in text)
        # Strong domain hooks for the sample tickets
        if label in {"billing", "payments"} and _any(text, ["charge", "invoice", "refund", "payment", "card"]):
            scores[label] += 1.2
        if label in {"technical", "bug_report", "engineering"} and _any(
            text, ["bug", "crash", "error", "stack", "safari", "api", "outage"]
        ):
            scores[label] += 1.2
        if label in {"shipping", "delivery"} and _any(text, ["ship", "delivery", "tracking", "package"]):
            scores[label] += 1.2
        if label in {"sales"} and _any(text, ["pricing", "upgrade", "enterprise", "demo"]):
            scores[label] += 1.0
        if label in {"other", "none_of_the_above"}:
            scores[label] = 0.08

    probs = _softmax(scores)
    choice = max(probs, key=probs.get)
    conf = max(probs.values()) - sorted(probs.values())[-2] if len(probs) > 1 else max(probs.values())
    return {
        "type": "choice",
        "choice": choice,
        "probabilities": {k: round(v, 4) for k, v in probs.items()},
        "confidence": round(_clip(conf + 0.35), 4),
    }


def _score_answer(text: str, q: dict[str, Any]) -> dict[str, Any]:
    criteria = q.get("criteria") or []
    if not isinstance(criteria, list) or len(criteria) < 2:
        raise ValueError("score questions need an ordered criteria list (2+)")

    n = len(criteria)
    # Bias toward higher levels when urgency / anger / blocking language appears
    intensity = 0.0
    intensity += 0.9 * _any(text, ["blocker", "blocking", "down", "outage", "cannot", "can't"])
    intensity += 0.7 * _any(text, ["angry", "furious", "unacceptable", "lawsuit", "cancel"])
    intensity += 0.5 * _any(text, ["asap", "urgent", "immediately"])
    intensity += 0.4 * _any(text, ["workaround", "degraded", "slow"])
    target = min(n - 1, intensity * (n - 1))

    raw = {str(i): max(0.02, 1.2 - abs(i - target)) for i in range(n)}
    probs = _softmax(raw)
    expected = sum(i * probs[str(i)] for i in range(n))
    conf = max(probs.values())
    return {
        "type": "score",
        "score": round(expected, 3),
        "legend": {str(i): criteria[i] for i in range(n)},
        "probabilities": {k: round(v, 4) for k, v in probs.items()},
        "confidence": round(_clip(conf), 4),
    }


def _any(text: str, words: list[str]) -> float:
    return 1.0 if any(w in text for w in words) else 0.0


def _clip(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def _softmax(scores: dict[str, float]) -> dict[str, float]:
    import math

    m = max(scores.values())
    exps = {k: math.exp(v - m) for k, v in scores.items()}
    z = sum(exps.values()) or 1.0
    return {k: v / z for k, v in exps.items()}

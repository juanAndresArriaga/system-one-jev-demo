# System One + Jev — tiny demo

Companion demo for [Introducing System One Models & Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev) (TypeSafe AI).

## The idea in one line

**Jev is a frontier-intelligence function call:** unstructured state in → typed probabilistic decisions out.

Existing LLMs are great at *chat* (System Two / slow, generative). **System One models** are built for *automation*: fast, structured decisions that ordinary software can branch on — without parsing free-form text or risking type errors.

```text
Support ticket / JSON state
        │
        ▼
   ┌─────────┐
   │   Jev   │  ← parallel answers (noul / choice / score)
   └─────────┘
        │
        ▼
your code: if / route / escalate
```

| | Typical LLM | System One (Jev) |
| --- | --- | --- |
| Output | Strings (then parse) | Typed values + probabilities |
| Sampling | Sequential tokens | Parallel decisions |
| Role in apps | Chat / agents | Smart `if` inside workflows |

## What this repo shows

A **support-ticket triage** workflow:

1. Feed ticket text as `state`
2. Ask several typed questions at once (`noul`, `choice`, `score`)
3. Branch in plain Python using probabilities / confidence

Runs **offline with a mock** by default (no API key). Pass `--live` + `TYPESAFE_API_KEY` to hit the real API when you have early access.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Mock demo (always works)
python demo.py

# Live Jev (needs early access)
export TYPESAFE_API_KEY=your_key
python demo.py --live
```

## Question primitives (from the post / docs)

| Type | Question | Returns |
| --- | --- | --- |
| **noul** | Is this true? | Probability in `[0, 1]` |
| **choice** | Which option? | Selected label + distribution + confidence |
| **score** | Where on this scale? | Weighted score + per-level probs + confidence |

## Project layout

```text
demo.py           # triage workflow + pretty print
jev_client.py     # mock + live HTTP client
requirements.txt
.env.example
```

## Notes

- Educational starter — API field names may evolve; check [TypeSafe docs](https://typesafe.ai) / early-access console.
- “Can’t hallucinate” here means **schema-safe outputs** (no invented enums), not “never wrong.”
- Live endpoint used: `POST https://api.typesafe.ai/v1/systemone` with `model: jev-latest`.

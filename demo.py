#!/usr/bin/env python3
"""System One / Jev mini-demo: support ticket → typed decisions → code branches.

Inspired by https://typesafe.ai/blog/introducing-system-one-models-and-jev
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from dotenv import load_dotenv

from jev_client import system_one

# Sample tickets — swap for your own unstructured state.
TICKETS = {
    "billing": (
        "Hi — I was charged twice for order A-104 on my Visa. "
        "Please refund the duplicate charge ASAP, this is urgent."
    ),
    "bug": (
        "The export button crashes the settings page in Safari. "
        "Works in Chrome. Steps: open Settings → Export → click Download. "
        "No workaround for our Safari-only customers."
    ),
    "calm": (
        "Quick question: does the Pro plan include SSO? "
        "Looking at upgrading next quarter."
    ),
}

# All independent questions in ONE call (speculative fan-out).
QUESTIONS: dict[str, Any] = {
    "needs_human": {
        "type": "noul",
        "instructions": "Does this ticket need a human agent right away?",
        "criteria": {
            "true": "Legal threat, payment dispute with anger, or unresolved outage",
            "false": "Routine question that automation or L1 can handle",
        },
    },
    "refund_requested": {
        "type": "noul",
        "instructions": "Does the customer ask for money back?",
    },
    "team": {
        "type": "choice",
        "instructions": "Which team should own this ticket?",
        "criteria": {
            "billing": "Charges, invoices, refunds, subscriptions",
            "technical": "Bugs, crashes, outages, integrations",
            "sales": "Pricing, upgrades, new accounts",
            "other": "None of the above",
        },
    },
    "urgency": {
        "type": "score",
        "instructions": "How urgent is this ticket?",
        "criteria": [
            "No deadline; informational",
            "Should be handled soon; customer waiting",
            "Blocking or money at risk; act immediately",
        ],
    },
}


def route(answers: dict[str, Any]) -> dict[str, Any]:
    """Plain software stays in control — Jev only supplies judgments."""
    team = answers["team"]
    urgency = answers["urgency"]
    refund = float(answers["refund_requested"].get("noul", 0))
    needs_human = float(answers["needs_human"].get("noul", 0))

    decision = {
        "queue": team.get("choice", "other"),
        "priority": "high" if urgency.get("score", 0) >= 1.5 else "normal",
        "auto_refund_candidate": refund >= 0.7 and team.get("choice") == "billing",
        "escalate_to_human": needs_human >= 0.6 or team.get("confidence", 1) < 0.45,
    }
    return decision


def print_report(name: str, state: str, result: dict[str, Any]) -> None:
    answers = result["answers"]
    decision = route(answers)
    print("=" * 64)
    print(f"ticket: {name}   source: {result['source']}   model: {result['model']}")
    print("-" * 64)
    print(state)
    print("-" * 64)
    print("answers:")
    print(json.dumps(answers, indent=2))
    print("-" * 64)
    print("code decision:")
    print(json.dumps(decision, indent=2))
    print()


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="System One / Jev support-triage demo")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Call TypeSafe API (needs TYPESAFE_API_KEY). Default: offline mock.",
    )
    parser.add_argument(
        "--ticket",
        choices=[*TICKETS.keys(), "all"],
        default="all",
        help="Which sample ticket to run",
    )
    args = parser.parse_args()

    names = list(TICKETS) if args.ticket == "all" else [args.ticket]
    for name in names:
        state = {"ticket": TICKETS[name]}
        result = system_one(state=state, questions=QUESTIONS, live=args.live)
        print_report(name, TICKETS[name], result)

    if not args.live:
        print("Tip: run with --live and TYPESAFE_API_KEY once you have early access.")


if __name__ == "__main__":
    main()

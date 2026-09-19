#!/usr/bin/env python3
"""Detach terminal AX through the existing audited Runtime disable Owner."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_aq_failed_retirement as retirement


ROOT = Path(__file__).resolve().parents[1]
retirement.STATE = ROOT.parent / ".aos-recovery-20260919/state/q-advisor-baseline/replacement-ay/retire-ax"
retirement.AQ_ID = "be884663-0dba-4d9b-aa56-84caaf01147d"
retirement.GENERATION = "a14c911b-6796-4d22-a3b0-1817cf502de9"
retirement.LOCK = "sha256:ae0c890abf2629daa136a615d9eadc4796e544f2e728ab4f567f0e7ebf65adc5"
retirement.FAILED_ATTEMPTS = (
    ("e5b99486-ecf6-460e-b2d3-de40e372d7c9", 61, "failed",
     "RECOVERABLE_INGRESS_DEADLINE_EXCEEDED", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-ax-retirement-20260919-v1"
retirement.DEFINITION_REVISION = 79
retirement.ACTIVE_ROUTE_REVISION = 123
retirement.ACTIVE_GROUP_REVISION = 150
retirement.DETACHED_ROUTE_REVISION = 125
retirement.DETACHED_GROUP_REVISION = 152


def setup():
    import a0v_ax_successor_business as current
    return current.setup()


retirement.setup = setup


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AQ_FAILED", "AX_TERMINAL").replace("AQ_NINE", "AX_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, default=str, indent=2))

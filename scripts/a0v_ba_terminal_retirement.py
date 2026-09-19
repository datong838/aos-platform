#!/usr/bin/env python3
"""Detach terminal BA through the existing audited Runtime disable Owner."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_aq_failed_retirement as retirement


ROOT = Path(__file__).resolve().parents[1]
retirement.STATE = ROOT.parent / ".aos-recovery-20260919/state/q-advisor-baseline/replacement-bb/retire-ba"
retirement.AQ_ID = "9110f69b-bb31-4d17-98e8-6c5ed1d9234f"
retirement.GENERATION = "197f5036-656a-4b58-a261-e93e2fffea18"
retirement.LOCK = "sha256:6fc165d534435f39488e59c47d615501c1b011beadb59a4a92ed1de76d769757"
retirement.FAILED_ATTEMPTS = (
    ("a000b48d-52d5-44ce-a3c5-159b40b1f9b6", 61, "abandoned",
     "ATTEMPT_LEASE_EXPIRED", None),
)
retirement.PREFIX = "a0v-qyh-terminal-ba-retirement-20260919-v1"
retirement.DEFINITION_REVISION = 85
retirement.ACTIVE_ROUTE_REVISION = 129
retirement.ACTIVE_GROUP_REVISION = 156
retirement.DETACHED_ROUTE_REVISION = 131
retirement.DETACHED_GROUP_REVISION = 158


def setup():
    import a0v_ba_successor_business as current
    return current.setup()


retirement.setup = setup


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AQ_FAILED", "BA_TERMINAL").replace("AQ_NINE", "BA_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, default=str, indent=2))

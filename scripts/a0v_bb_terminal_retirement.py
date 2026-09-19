#!/usr/bin/env python3
"""Detach terminal BB through the existing audited Runtime disable Owner."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_aq_failed_retirement as retirement


ROOT = Path(__file__).resolve().parents[1]
retirement.STATE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/replacement-bc/retire-bb"
retirement.AQ_ID = "09752ccf-d51a-44b7-a5bf-62b5ab8ec5d6"
retirement.GENERATION = "099c4d17-47fb-4c07-9ef1-c627ca7b4239"
retirement.LOCK = "sha256:f5ae36a5e7db006f81b87af036c5e83b6a3ed7f0f714182b15b598cd9f03fe37"
retirement.FAILED_ATTEMPTS = (
    ("ee8dfb28-6b51-47da-9003-2c70d51ea08e", 61, "abandoned",
     "ATTEMPT_LEASE_EXPIRED", None),
)
retirement.PREFIX = "a0v-qyh-terminal-bb-retirement-20260920-v1"
retirement.DEFINITION_REVISION = 88
retirement.ACTIVE_ROUTE_REVISION = 132
retirement.ACTIVE_GROUP_REVISION = 159
retirement.DETACHED_ROUTE_REVISION = 134
retirement.DETACHED_GROUP_REVISION = 161


def setup():
    import a0v_bb_successor_business as current
    return current.setup()


retirement.setup = setup


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AQ_FAILED", "BB_TERMINAL").replace("AQ_NINE", "BB_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, default=str, indent=2))

#!/usr/bin/env python3
"""Retire BJ's exact single abandoned terminal attempt boundary."""
from __future__ import annotations

import argparse
import json

import a0v_aq_failed_retirement as retirement
import a0v_bj_successor_business as bj_successor


retirement.STATE = bj_successor.STATE.parent / "retire-bj"
retirement.AQ_ID = "2c3972b1-67c1-400d-aa63-b90de369f5de"
retirement.GENERATION = "8dafd4ae-d42b-4f2f-accb-b5a49e7c9a3b"
retirement.LOCK = "sha256:d01e0d465ac65672a7edac4be6b453d16958037d15fff75220b6d5dee4458128"
retirement.FAILED_ATTEMPTS = (
    ("6746bf55-daf2-4bc6-a8fe-038f3ff0bcba", 61, "abandoned",
     "ATTEMPT_LEASE_EXPIRED", None),
)
retirement.PREFIX = "a0v-qyh-terminal-bj-retirement-20260920-v1"
retirement.DEFINITION_REVISION = 112
retirement.ACTIVE_ROUTE_REVISION = 156
retirement.ACTIVE_GROUP_REVISION = 183
retirement.DETACHED_ROUTE_REVISION = 158
retirement.DETACHED_GROUP_REVISION = 185


def setup():
    return bj_successor.setup()


retirement.setup = setup


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AQ_FAILED", "BJ_TERMINAL").replace("AQ_NINE", "BJ_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

#!/usr/bin/env python3
"""Retire BE's exact terminal attempt boundary."""
from __future__ import annotations

import argparse
import json

import a0v_aq_failed_retirement as retirement
import a0v_be_successor_business as be_successor


retirement.STATE = be_successor.STATE.parent / "retire-be"
retirement.AQ_ID = "1a0f801f-d8f3-43af-a31e-5c9fc8161d6d"
retirement.GENERATION = "93349d9b-ad61-4919-9cbd-e1e9b02545bb"
retirement.LOCK = "sha256:30602cd6e4b4adebd8b1710abc6cd5204284ab62d12598fde4fa527a72b8e05d"
retirement.FAILED_ATTEMPTS = (("041843a3-2cf0-4211-bc16-00e823c210bc", 61, "abandoned",
                               "ATTEMPT_LEASE_EXPIRED", None),)
retirement.PREFIX = "a0v-qyh-terminal-be-retirement-20260920-v1"
retirement.DEFINITION_REVISION = 97
retirement.ACTIVE_ROUTE_REVISION = 141
retirement.ACTIVE_GROUP_REVISION = 168
retirement.DETACHED_ROUTE_REVISION = 143
retirement.DETACHED_GROUP_REVISION = 170


def setup():
    return be_successor.setup()


retirement.setup = setup


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AQ_FAILED", "BE_TERMINAL").replace("AQ_NINE", "BE_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

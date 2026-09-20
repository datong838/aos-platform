#!/usr/bin/env python3
"""Retire BG's exact single abandoned terminal attempt boundary."""
from __future__ import annotations

import argparse
import json

import a0v_aq_failed_retirement as retirement
import a0v_bg_successor_business as bg_successor


retirement.STATE = bg_successor.STATE.parent / "retire-bg"
retirement.AQ_ID = "c52ab6db-176e-4378-ac88-2ee1bfc58487"
retirement.GENERATION = "477c3f92-06f0-4dae-9445-ce6d09c3f462"
retirement.LOCK = "sha256:0e1880beeac4b28399b828c79b387c32e0be1cc41e982f786a8ddd8d04f88eb3"
retirement.FAILED_ATTEMPTS = (
    ("a42bc506-7e3c-48cd-bde7-1eb0b1adc93f", 61, "abandoned",
     "ATTEMPT_LEASE_EXPIRED", None),
)
retirement.PREFIX = "a0v-qyh-terminal-bg-retirement-20260920-v1"
retirement.DEFINITION_REVISION = 103
retirement.ACTIVE_ROUTE_REVISION = 147
retirement.ACTIVE_GROUP_REVISION = 174
retirement.DETACHED_ROUTE_REVISION = 149
retirement.DETACHED_GROUP_REVISION = 176


def setup():
    return bg_successor.setup()


retirement.setup = setup


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AQ_FAILED", "BG_TERMINAL").replace("AQ_NINE", "BG_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

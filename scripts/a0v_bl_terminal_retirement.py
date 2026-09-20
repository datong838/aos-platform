#!/usr/bin/env python3
"""Retire BL's exact single abandoned terminal attempt boundary."""
from __future__ import annotations

import argparse
import json

import a0v_aq_failed_retirement as retirement
import a0v_bl_successor_business as bl_successor


retirement.STATE = bl_successor.STATE.parent / "retire-bl"
retirement.AQ_ID = "ac9b3ec8-68ad-4e05-9f30-b2f8f6a473bc"
retirement.GENERATION = "116d12fc-93bc-4071-a973-fdc6830ea8b1"
retirement.LOCK = "sha256:47af46b5658b7952f9d3068466ba06c6203e51fef899c5d661026230893b334e"
retirement.FAILED_ATTEMPTS = (
    ("06352972-8c80-4291-aece-2474209e6a76", 46, "abandoned",
     "ATTEMPT_LEASE_EXPIRED", None),
)
retirement.PREFIX = "a0v-qyh-terminal-bl-retirement-20260920-v1"
retirement.DEFINITION_REVISION = 118
retirement.ACTIVE_ROUTE_REVISION = 162
retirement.ACTIVE_GROUP_REVISION = 189
retirement.DETACHED_ROUTE_REVISION = 164
retirement.DETACHED_GROUP_REVISION = 191


def setup():
    return bl_successor.setup()


retirement.setup = setup


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AQ_FAILED", "BL_TERMINAL").replace("AQ_NINE", "BL_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

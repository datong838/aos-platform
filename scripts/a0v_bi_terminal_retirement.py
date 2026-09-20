#!/usr/bin/env python3
"""Retire BI's exact single abandoned terminal attempt boundary."""
from __future__ import annotations

import argparse
import json

import a0v_aq_failed_retirement as retirement
import a0v_bi_successor_business as bi_successor


retirement.STATE = bi_successor.STATE.parent / "retire-bi"
retirement.AQ_ID = "8ca245a1-8420-4590-b9e4-f92256fc22ce"
retirement.GENERATION = "6f527122-a4a5-4056-a4e6-ca888f4b64d7"
retirement.LOCK = "sha256:969bb16d93cf922278bb2424c529cda2221eec1235d583b29ddc7f32991c9745"
retirement.FAILED_ATTEMPTS = (
    ("1f8e44c0-c5a7-4099-89a0-6f4998589e4e", 61, "abandoned",
     "ATTEMPT_LEASE_EXPIRED", None),
)
retirement.PREFIX = "a0v-qyh-terminal-bi-retirement-20260920-v1"
retirement.DEFINITION_REVISION = 109
retirement.ACTIVE_ROUTE_REVISION = 153
retirement.ACTIVE_GROUP_REVISION = 180
retirement.DETACHED_ROUTE_REVISION = 155
retirement.DETACHED_GROUP_REVISION = 182


def setup():
    return bi_successor.setup()


retirement.setup = setup


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AQ_FAILED", "BI_TERMINAL").replace("AQ_NINE", "BI_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

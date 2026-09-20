#!/usr/bin/env python3
"""Retire BK's exact single cancelled terminal attempt boundary."""
from __future__ import annotations

import argparse
import json

import a0v_aq_failed_retirement as retirement
import a0v_bk_successor_business as bk_successor


retirement.STATE = bk_successor.STATE.parent / "retire-bk"
retirement.AQ_ID = "8c78f903-ebd8-4589-97a0-afad76e209e0"
retirement.GENERATION = "9ea4ba9d-1ef8-45a6-9060-1e4f37c87038"
retirement.LOCK = "sha256:462bc93fcd577556199e60c70eb21b3e5ae539b310f101aeb6095b9613babf71"
retirement.FAILED_ATTEMPTS = (
    ("c0b032b7-30c1-4260-9b67-99e298347dea", 13, "failed",
     "RECOVERABLE_INGRESS_CANCELLED", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-bk-retirement-20260920-v1"
retirement.DEFINITION_REVISION = 115
retirement.ACTIVE_ROUTE_REVISION = 159
retirement.ACTIVE_GROUP_REVISION = 186
retirement.DETACHED_ROUTE_REVISION = 161
retirement.DETACHED_GROUP_REVISION = 188


def setup():
    return bk_successor.setup()


retirement.setup = setup


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AQ_FAILED", "BK_TERMINAL").replace("AQ_NINE", "BK_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

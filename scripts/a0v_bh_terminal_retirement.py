#!/usr/bin/env python3
"""Retire BH's exact single failed terminal attempt boundary."""
from __future__ import annotations

import argparse
import json

import a0v_aq_failed_retirement as retirement
import a0v_bh_successor_business as bh_successor


retirement.STATE = bh_successor.STATE.parent / "retire-bh"
retirement.AQ_ID = "7b7d4319-e639-48c9-971b-0efbfb9251ef"
retirement.GENERATION = "f6023b7c-ca6f-49ac-b9ff-4dcbca62745c"
retirement.LOCK = "sha256:c920a20eec94c3f9da2030da31a05f5b8f314f8e9264c5d5d8b4bcc02e4c28fa"
retirement.FAILED_ATTEMPTS = (
    ("6d8395b6-b04b-4aa3-b002-9b3618e1eaf3", 61, "failed",
     "RECOVERABLE_INGRESS_DEADLINE_EXCEEDED", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-bh-retirement-20260920-v1"
retirement.DEFINITION_REVISION = 106
retirement.ACTIVE_ROUTE_REVISION = 150
retirement.ACTIVE_GROUP_REVISION = 177
retirement.DETACHED_ROUTE_REVISION = 152
retirement.DETACHED_GROUP_REVISION = 179


def setup():
    return bh_successor.setup()


retirement.setup = setup


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AQ_FAILED", "BH_TERMINAL").replace("AQ_NINE", "BH_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

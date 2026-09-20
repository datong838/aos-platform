#!/usr/bin/env python3
"""Retire BF's exact dual-terminal attempt boundary."""
from __future__ import annotations

import argparse
import json

import a0v_aq_failed_retirement as retirement
import a0v_bf_successor_business as bf_successor


retirement.STATE = bf_successor.STATE.parent / "retire-bf"
retirement.AQ_ID = "98a16beb-6342-48bd-9e12-989f3612ca00"
retirement.GENERATION = "e33e0a9e-7296-4374-9aa9-113f1ed79b5f"
retirement.LOCK = "sha256:6cb2cef564ead4ace9dbeb091512b4f6cf0d8a8508782308a8cacea89bc921ed"
retirement.FAILED_ATTEMPTS = (
    ("0a79f73d-7243-4778-90af-2e2109115e73", 61, "failed",
     "RECOVERABLE_INGRESS_DEADLINE_EXCEEDED", "IngressJournalConflict"),
    ("b61340d4-391f-415d-ac77-65ed8f72321d", 10, "failed",
     "RECOVERABLE_INGRESS_CANCELLED", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-bf-retirement-20260920-v1"
retirement.DEFINITION_REVISION = 100
retirement.ACTIVE_ROUTE_REVISION = 144
retirement.ACTIVE_GROUP_REVISION = 171
retirement.DETACHED_ROUTE_REVISION = 146
retirement.DETACHED_GROUP_REVISION = 173


def setup():
    return bf_successor.setup()


retirement.setup = setup


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AQ_FAILED", "BF_TERMINAL").replace("AQ_NINE", "BF_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

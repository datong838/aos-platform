#!/usr/bin/env python3
"""Retire BD's exact terminal attempt boundary."""
from __future__ import annotations

import argparse
import json

import a0v_aq_failed_retirement as retirement
import a0v_bd_successor_business as bd_successor


retirement.STATE = bd_successor.STATE.parent / "retire-bd"
retirement.AQ_ID = "c2d6ef97-30ec-4980-9421-54a899607853"
retirement.GENERATION = "f5e01f1d-e6c5-425a-9145-6f7a82ec65e5"
retirement.LOCK = "sha256:0acab1c9950e014737c8e5814750bca0118bf265e9dfeb382a52d32b45a71547"
retirement.FAILED_ATTEMPTS = (("f1e89789-86ca-4cd5-9854-c75e1c41db94", 61, "failed",
                               "RECOVERABLE_INGRESS_DEADLINE_EXCEEDED", "IngressJournalConflict"),)
retirement.PREFIX = "a0v-qyh-terminal-bd-retirement-20260920-v1"
retirement.DEFINITION_REVISION = 94
retirement.ACTIVE_ROUTE_REVISION = 138
retirement.ACTIVE_GROUP_REVISION = 165
retirement.DETACHED_ROUTE_REVISION = 140
retirement.DETACHED_GROUP_REVISION = 167


def setup():
    return bd_successor.setup()


retirement.setup = setup


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AQ_FAILED", "BD_TERMINAL").replace("AQ_NINE", "BD_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

#!/usr/bin/env python3
"""Retire DB's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_db_replacement_recovery as db_replacement
import a0v_db_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-db"
retirement.AR_ID = successor.DB_ID
retirement.GENERATION = successor.DB_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("1679bef7-84fc-408c-9bb2-d202ba68dc91", 4, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-db-retirement-20260921-v1"
retirement.DEFINITION_REVISION = 226
retirement.ACTIVE_ROUTE_REVISION = 285
retirement.ACTIVE_GROUP_REVISION = 312
retirement.DETACHED_ROUTE_REVISION = 287
retirement.DETACHED_GROUP_REVISION = 314


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = db_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = db_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = db_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "DB_TERMINAL").replace(
        "AR_NINE", "DB_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

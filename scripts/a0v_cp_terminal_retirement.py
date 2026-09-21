#!/usr/bin/env python3
"""Retire CP's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_cp_replacement_recovery as cp_replacement
import a0v_cp_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-cp"
retirement.AR_ID = successor.CP_ID
retirement.GENERATION = successor.CP_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("4c63e9fd-6f11-461d-a753-87962f5306ad", 4, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-cp-retirement-20260921-v1"
retirement.DEFINITION_REVISION = 193
retirement.ACTIVE_ROUTE_REVISION = 249
retirement.ACTIVE_GROUP_REVISION = 276
retirement.DETACHED_ROUTE_REVISION = 251
retirement.DETACHED_GROUP_REVISION = 278


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = cp_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = cp_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = cp_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "CP_TERMINAL").replace(
        "AR_NINE", "CP_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

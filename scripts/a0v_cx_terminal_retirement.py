#!/usr/bin/env python3
"""Retire CX's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_cx_replacement_recovery as cx_replacement
import a0v_cx_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-cx"
retirement.AR_ID = successor.CX_ID
retirement.GENERATION = successor.CX_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("715c69b5-db78-4503-9f6e-2e6a5f132b1d", 4, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-cx-retirement-20260921-v1"
retirement.DEFINITION_REVISION = 214
retirement.ACTIVE_ROUTE_REVISION = 273
retirement.ACTIVE_GROUP_REVISION = 300
retirement.DETACHED_ROUTE_REVISION = 275
retirement.DETACHED_GROUP_REVISION = 302


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = cx_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = cx_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = cx_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "CX_TERMINAL").replace(
        "AR_NINE", "CX_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

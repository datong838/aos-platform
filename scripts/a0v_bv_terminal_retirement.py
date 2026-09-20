#!/usr/bin/env python3
"""Retire BV's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_bv_replacement_recovery as bv_replacement
import a0v_bv_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-bv"
retirement.AR_ID = successor.BV_ID
retirement.GENERATION = successor.BV_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("3afcfcae-b78c-4d15-8c64-4ec4e53325f3", 4, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-bv-retirement-20260921-v1"
retirement.DEFINITION_REVISION = 133
retirement.ACTIVE_ROUTE_REVISION = 189
retirement.ACTIVE_GROUP_REVISION = 216
retirement.DETACHED_ROUTE_REVISION = 191
retirement.DETACHED_GROUP_REVISION = 218


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = bv_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = bv_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = bv_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "BV_TERMINAL").replace(
        "AR_NINE", "BV_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

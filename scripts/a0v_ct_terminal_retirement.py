#!/usr/bin/env python3
"""Retire CT's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_ct_replacement_recovery as ct_replacement
import a0v_ct_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-ct"
retirement.AR_ID = successor.CT_ID
retirement.GENERATION = successor.CT_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("5b22aca6-70b5-46e0-b5aa-0f477964df96", 5, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-ct-retirement-20260921-v1"
retirement.DEFINITION_REVISION = 202
retirement.ACTIVE_ROUTE_REVISION = 261
retirement.ACTIVE_GROUP_REVISION = 288
retirement.DETACHED_ROUTE_REVISION = 263
retirement.DETACHED_GROUP_REVISION = 290


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = ct_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = ct_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = ct_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "CT_TERMINAL").replace(
        "AR_NINE", "CT_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

#!/usr/bin/env python3
"""Retire CW's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_cw_replacement_recovery as cw_replacement
import a0v_cw_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-cw"
retirement.AR_ID = successor.CW_ID
retirement.GENERATION = successor.CW_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("0f9c30e6-012d-4a08-9aed-f7b0e0492c31", 4, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-cw-retirement-20260921-v1"
retirement.DEFINITION_REVISION = 211
retirement.ACTIVE_ROUTE_REVISION = 270
retirement.ACTIVE_GROUP_REVISION = 297
retirement.DETACHED_ROUTE_REVISION = 272
retirement.DETACHED_GROUP_REVISION = 299


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = cw_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = cw_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = cw_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "CW_TERMINAL").replace(
        "AR_NINE", "CW_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

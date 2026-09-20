#!/usr/bin/env python3
"""Retire BX's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_bx_replacement_recovery as bx_replacement
import a0v_bx_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-bx"
retirement.AR_ID = successor.BX_ID
retirement.GENERATION = successor.BX_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("dedb3bf6-46ef-4b25-9733-1197ea043d26", 4, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-bx-retirement-20260921-v1"
retirement.DEFINITION_REVISION = 139
retirement.ACTIVE_ROUTE_REVISION = 195
retirement.ACTIVE_GROUP_REVISION = 222
retirement.DETACHED_ROUTE_REVISION = 197
retirement.DETACHED_GROUP_REVISION = 224


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = bx_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = bx_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = bx_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "BX_TERMINAL").replace(
        "AR_NINE", "BX_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

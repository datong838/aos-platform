#!/usr/bin/env python3
"""Retire DA's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_da_replacement_recovery as da_replacement
import a0v_da_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-da"
retirement.AR_ID = successor.DA_ID
retirement.GENERATION = successor.DA_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("f61804b2-7863-4371-ac66-80e0a6eb1d0d", 4, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-da-retirement-20260921-v1"
retirement.DEFINITION_REVISION = 223
retirement.ACTIVE_ROUTE_REVISION = 282
retirement.ACTIVE_GROUP_REVISION = 309
retirement.DETACHED_ROUTE_REVISION = 284
retirement.DETACHED_GROUP_REVISION = 311


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = da_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = da_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = da_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "DA_TERMINAL").replace(
        "AR_NINE", "DA_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

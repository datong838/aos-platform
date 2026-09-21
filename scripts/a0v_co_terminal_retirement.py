#!/usr/bin/env python3
"""Retire CO's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_co_replacement_recovery as co_replacement
import a0v_co_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-co"
retirement.AR_ID = successor.CO_ID
retirement.GENERATION = successor.CO_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("f3061da8-baee-4b3a-8307-88d835d42cca", 4, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-co-retirement-20260921-v1"
retirement.DEFINITION_REVISION = 190
retirement.ACTIVE_ROUTE_REVISION = 246
retirement.ACTIVE_GROUP_REVISION = 273
retirement.DETACHED_ROUTE_REVISION = 248
retirement.DETACHED_GROUP_REVISION = 275


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = co_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = co_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = co_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "CO_TERMINAL").replace(
        "AR_NINE", "CO_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

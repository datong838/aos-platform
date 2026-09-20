#!/usr/bin/env python3
"""Retire BY's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_by_replacement_recovery as by_replacement
import a0v_by_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-by"
retirement.AR_ID = successor.BY_ID
retirement.GENERATION = successor.BY_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("72876c75-a853-488a-b1e6-4c334b635f91", 4, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-by-retirement-20260921-v1"
retirement.DEFINITION_REVISION = 142
retirement.ACTIVE_ROUTE_REVISION = 198
retirement.ACTIVE_GROUP_REVISION = 225
retirement.DETACHED_ROUTE_REVISION = 200
retirement.DETACHED_GROUP_REVISION = 227


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = by_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = by_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = by_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "BY_TERMINAL").replace(
        "AR_NINE", "BY_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

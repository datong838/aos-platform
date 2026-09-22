#!/usr/bin/env python3
"""Retire DD's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_dd_replacement_recovery as dd_replacement
import a0v_dd_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-dd"
retirement.AR_ID = successor.DD_ID
retirement.GENERATION = successor.DD_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("a2396b18-ade6-4c91-912d-1c953d8e17b5", 4, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-dd-retirement-20260922-v1"
retirement.DEFINITION_REVISION = 232
retirement.ACTIVE_ROUTE_REVISION = 291
retirement.ACTIVE_GROUP_REVISION = 318
retirement.DETACHED_ROUTE_REVISION = 293
retirement.DETACHED_GROUP_REVISION = 320


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = dd_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = dd_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = dd_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "DD_TERMINAL").replace(
        "AR_NINE", "DD_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

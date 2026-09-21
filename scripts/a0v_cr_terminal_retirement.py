#!/usr/bin/env python3
"""Retire CR's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_cr_replacement_recovery as cr_replacement
import a0v_cr_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-cr"
retirement.AR_ID = successor.CR_ID
retirement.GENERATION = successor.CR_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("11e98b8f-d898-4b1b-a6fc-c210bb44e5d7", 5, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-cr-retirement-20260921-v1"
retirement.DEFINITION_REVISION = 196
retirement.ACTIVE_ROUTE_REVISION = 255
retirement.ACTIVE_GROUP_REVISION = 282
retirement.DETACHED_ROUTE_REVISION = 257
retirement.DETACHED_GROUP_REVISION = 284


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = cr_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = cr_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = cr_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "CR_TERMINAL").replace(
        "AR_NINE", "CR_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

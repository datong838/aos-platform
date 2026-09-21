#!/usr/bin/env python3
"""Retire CC's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_cc_replacement_recovery as cc_replacement
import a0v_cc_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-cc"
retirement.AR_ID = successor.CC_ID
retirement.GENERATION = successor.CC_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("74ee33d8-b0d4-444a-9c01-ba31e9358552", 4, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-cc-retirement-20260921-v1"
retirement.DEFINITION_REVISION = 154
retirement.ACTIVE_ROUTE_REVISION = 210
retirement.ACTIVE_GROUP_REVISION = 237
retirement.DETACHED_ROUTE_REVISION = 212
retirement.DETACHED_GROUP_REVISION = 239


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = cc_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = cc_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = cc_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "CC_TERMINAL").replace(
        "AR_NINE", "CC_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

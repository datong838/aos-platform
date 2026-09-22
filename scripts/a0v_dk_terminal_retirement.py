#!/usr/bin/env python3
"""Retire DK's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_dk_replacement_recovery as dk_replacement
import a0v_dk_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-dk"
retirement.AR_ID = successor.DK_ID
retirement.GENERATION = successor.DK_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("7c7282e0-aa83-45e6-99ac-ae996f86b1b7", 5, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-dk-retirement-20260922-v1"
retirement.DEFINITION_REVISION = 253
retirement.ACTIVE_ROUTE_REVISION = 312
retirement.ACTIVE_GROUP_REVISION = 339
retirement.DETACHED_ROUTE_REVISION = 314
retirement.DETACHED_GROUP_REVISION = 341


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = dk_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = dk_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = dk_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "DK_TERMINAL").replace(
        "AR_NINE", "DK_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

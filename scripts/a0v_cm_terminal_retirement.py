#!/usr/bin/env python3
"""Retire CM's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_cm_replacement_recovery as cm_replacement
import a0v_cm_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-cm"
retirement.AR_ID = successor.CM_ID
retirement.GENERATION = successor.CM_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("da4fed10-4cdc-4147-8595-d2f40c568419", 4, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-cm-retirement-20260921-v1"
retirement.DEFINITION_REVISION = 184
retirement.ACTIVE_ROUTE_REVISION = 240
retirement.ACTIVE_GROUP_REVISION = 267
retirement.DETACHED_ROUTE_REVISION = 242
retirement.DETACHED_GROUP_REVISION = 269


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = cm_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = cm_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = cm_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "CM_TERMINAL").replace(
        "AR_NINE", "CM_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

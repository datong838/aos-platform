#!/usr/bin/env python3
"""Retire CB's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_cb_replacement_recovery as cb_replacement
import a0v_cb_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-cb"
retirement.AR_ID = successor.CB_ID
retirement.GENERATION = successor.CB_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("727af369-a8ce-4500-86a7-1cf412a42cb3", 4, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-cb-retirement-20260921-v1"
retirement.DEFINITION_REVISION = 151
retirement.ACTIVE_ROUTE_REVISION = 207
retirement.ACTIVE_GROUP_REVISION = 234
retirement.DETACHED_ROUTE_REVISION = 209
retirement.DETACHED_GROUP_REVISION = 236


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = cb_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = cb_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = cb_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "CB_TERMINAL").replace(
        "AR_NINE", "CB_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

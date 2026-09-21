#!/usr/bin/env python3
"""Retire CH's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_ch_replacement_recovery as ch_replacement
import a0v_ch_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-ch"
retirement.AR_ID = successor.CH_ID
retirement.GENERATION = successor.CH_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("0be8900c-4e4f-41c7-a93b-7dbfecb2bfe6", 4, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-ch-retirement-20260921-v1"
retirement.DEFINITION_REVISION = 169
retirement.ACTIVE_ROUTE_REVISION = 225
retirement.ACTIVE_GROUP_REVISION = 252
retirement.DETACHED_ROUTE_REVISION = 227
retirement.DETACHED_GROUP_REVISION = 254


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = ch_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = ch_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = ch_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "CH_TERMINAL").replace(
        "AR_NINE", "CH_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

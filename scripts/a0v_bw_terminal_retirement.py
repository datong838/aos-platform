#!/usr/bin/env python3
"""Retire BW's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_bw_replacement_recovery as bw_replacement
import a0v_bw_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-bw"
retirement.AR_ID = successor.BW_ID
retirement.GENERATION = successor.BW_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("4e3846d8-28b2-4c50-934b-8383df598956", 4, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-bw-retirement-20260921-v1"
retirement.DEFINITION_REVISION = 136
retirement.ACTIVE_ROUTE_REVISION = 192
retirement.ACTIVE_GROUP_REVISION = 219
retirement.DETACHED_ROUTE_REVISION = 194
retirement.DETACHED_GROUP_REVISION = 221


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = bw_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = bw_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = bw_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "BW_TERMINAL").replace(
        "AR_NINE", "BW_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

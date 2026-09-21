#!/usr/bin/env python3
"""Retire CN's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_cn_replacement_recovery as cn_replacement
import a0v_cn_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-cn"
retirement.AR_ID = successor.CN_ID
retirement.GENERATION = successor.CN_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("1cf52d77-baa9-49a5-9315-d705b864c8a0", 5, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-cn-retirement-20260921-v1"
retirement.DEFINITION_REVISION = 187
retirement.ACTIVE_ROUTE_REVISION = 243
retirement.ACTIVE_GROUP_REVISION = 270
retirement.DETACHED_ROUTE_REVISION = 245
retirement.DETACHED_GROUP_REVISION = 272


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = cn_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = cn_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = cn_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "CN_TERMINAL").replace(
        "AR_NINE", "CN_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

#!/usr/bin/env python3
"""Retire CJ's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_cj_replacement_recovery as cj_replacement
import a0v_cj_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-cj"
retirement.AR_ID = successor.CJ_ID
retirement.GENERATION = successor.CJ_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("d0326f13-2ccb-49c0-ade9-0729dc188717", 5, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-cj-retirement-20260921-v1"
retirement.DEFINITION_REVISION = 175
retirement.ACTIVE_ROUTE_REVISION = 231
retirement.ACTIVE_GROUP_REVISION = 258
retirement.DETACHED_ROUTE_REVISION = 233
retirement.DETACHED_GROUP_REVISION = 260


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = cj_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = cj_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = cj_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "CJ_TERMINAL").replace(
        "AR_NINE", "CJ_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

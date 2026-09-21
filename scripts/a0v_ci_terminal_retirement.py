#!/usr/bin/env python3
"""Retire CI's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_ci_replacement_recovery as ci_replacement
import a0v_ci_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-ci"
retirement.AR_ID = successor.CI_ID
retirement.GENERATION = successor.CI_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("4c67a2b5-34a6-47f7-9cc6-e59ce718d491", 4, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-ci-retirement-20260921-v1"
retirement.DEFINITION_REVISION = 172
retirement.ACTIVE_ROUTE_REVISION = 228
retirement.ACTIVE_GROUP_REVISION = 255
retirement.DETACHED_ROUTE_REVISION = 230
retirement.DETACHED_GROUP_REVISION = 257


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = ci_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = ci_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = ci_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "CI_TERMINAL").replace(
        "AR_NINE", "CI_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

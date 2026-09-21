#!/usr/bin/env python3
"""Retire CY's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_cy_replacement_recovery as cy_replacement
import a0v_cy_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-cy"
retirement.AR_ID = successor.CY_ID
retirement.GENERATION = successor.CY_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("35c2b886-7d38-4ca7-9db6-3f90815420a2", 4, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-cy-retirement-20260921-v1"
retirement.DEFINITION_REVISION = 217
retirement.ACTIVE_ROUTE_REVISION = 276
retirement.ACTIVE_GROUP_REVISION = 303
retirement.DETACHED_ROUTE_REVISION = 278
retirement.DETACHED_GROUP_REVISION = 305


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = cy_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = cy_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = cy_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "CY_TERMINAL").replace(
        "AR_NINE", "CY_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

#!/usr/bin/env python3
"""Retire CU's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_cu_replacement_recovery as cu_replacement
import a0v_cu_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-cu"
retirement.AR_ID = successor.CU_ID
retirement.GENERATION = successor.CU_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("e845cb50-44dd-489c-a85d-85a8932b4d0f", 5, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-cu-retirement-20260921-v1"
retirement.DEFINITION_REVISION = 205
retirement.ACTIVE_ROUTE_REVISION = 264
retirement.ACTIVE_GROUP_REVISION = 291
retirement.DETACHED_ROUTE_REVISION = 266
retirement.DETACHED_GROUP_REVISION = 293


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = cu_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = cu_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = cu_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "CU_TERMINAL").replace(
        "AR_NINE", "CU_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

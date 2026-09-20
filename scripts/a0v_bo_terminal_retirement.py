#!/usr/bin/env python3
"""Retire BO's exact two failed terminal attempts through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_bo_replacement_recovery as bo_replacement
import a0v_bo_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-bo"
retirement.AR_ID = successor.BO_ID
retirement.GENERATION = successor.BO_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("57881020-86fe-44cc-be3e-2cd90787205e", 2, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "RuntimeConflict"),
    ("9d1fc481-7eb2-426f-8b0b-65627f06ec97", 2, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "RuntimeConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-bo-retirement-20260920-v1"
retirement.DEFINITION_REVISION = 121
retirement.ACTIVE_ROUTE_REVISION = 168
retirement.ACTIVE_GROUP_REVISION = 195
retirement.DETACHED_ROUTE_REVISION = 170
retirement.DETACHED_GROUP_REVISION = 197


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = bo_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = bo_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = bo_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "BO_TERMINAL").replace(
        "AR_NINE", "BO_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

#!/usr/bin/env python3
"""Retire CL's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_cl_replacement_recovery as cl_replacement
import a0v_cl_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-cl"
retirement.AR_ID = successor.CL_ID
retirement.GENERATION = successor.CL_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("bf2ff936-6c93-4712-93cb-30dd312f11eb", 5, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-cl-retirement-20260921-v1"
retirement.DEFINITION_REVISION = 181
retirement.ACTIVE_ROUTE_REVISION = 237
retirement.ACTIVE_GROUP_REVISION = 264
retirement.DETACHED_ROUTE_REVISION = 239
retirement.DETACHED_GROUP_REVISION = 266


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = cl_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = cl_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = cl_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "CL_TERMINAL").replace(
        "AR_NINE", "CL_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

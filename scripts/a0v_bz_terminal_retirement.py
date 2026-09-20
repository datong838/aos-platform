#!/usr/bin/env python3
"""Retire BZ's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_bz_replacement_recovery as bz_replacement
import a0v_bz_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-bz"
retirement.AR_ID = successor.BZ_ID
retirement.GENERATION = successor.BZ_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("b7044a35-43f8-4089-ba79-4da3d92cbf64", 4, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-bz-retirement-20260921-v1"
retirement.DEFINITION_REVISION = 145
retirement.ACTIVE_ROUTE_REVISION = 201
retirement.ACTIVE_GROUP_REVISION = 228
retirement.DETACHED_ROUTE_REVISION = 203
retirement.DETACHED_GROUP_REVISION = 230


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = bz_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = bz_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = bz_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "BZ_TERMINAL").replace(
        "AR_NINE", "BZ_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

#!/usr/bin/env python3
"""Retire CZ's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_cz_replacement_recovery as cz_replacement
import a0v_cz_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-cz"
retirement.AR_ID = successor.CZ_ID
retirement.GENERATION = successor.CZ_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("d5ca4825-decb-4263-ac0f-f87d2fe8a7b0", 4, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-cz-retirement-20260921-v1"
retirement.DEFINITION_REVISION = 220
retirement.ACTIVE_ROUTE_REVISION = 279
retirement.ACTIVE_GROUP_REVISION = 306
retirement.DETACHED_ROUTE_REVISION = 281
retirement.DETACHED_GROUP_REVISION = 308


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = cz_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = cz_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = cz_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "CZ_TERMINAL").replace(
        "AR_NINE", "CZ_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

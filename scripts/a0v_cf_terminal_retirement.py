#!/usr/bin/env python3
"""Retire CF's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_cf_replacement_recovery as cf_replacement
import a0v_cf_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-cf"
retirement.AR_ID = successor.CF_ID
retirement.GENERATION = successor.CF_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("d16e9452-0f4b-40cc-97f0-316841dfee29", 4, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-cf-retirement-20260921-v1"
retirement.DEFINITION_REVISION = 163
retirement.ACTIVE_ROUTE_REVISION = 219
retirement.ACTIVE_GROUP_REVISION = 246
retirement.DETACHED_ROUTE_REVISION = 221
retirement.DETACHED_GROUP_REVISION = 248


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = cf_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = cf_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = cf_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "CF_TERMINAL").replace(
        "AR_NINE", "CF_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

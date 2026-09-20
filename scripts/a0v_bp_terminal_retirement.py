#!/usr/bin/env python3
"""Retire BP's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_bp_replacement_recovery as bp_replacement
import a0v_bp_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-bp"
retirement.AR_ID = successor.BP_ID
retirement.GENERATION = successor.BP_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("051397ad-7027-4ee5-9d4c-f32374841cd9", 5, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-bp-retirement-20260920-v1"
retirement.DEFINITION_REVISION = 124
retirement.ACTIVE_ROUTE_REVISION = 171
retirement.ACTIVE_GROUP_REVISION = 198
retirement.DETACHED_ROUTE_REVISION = 173
retirement.DETACHED_GROUP_REVISION = 200


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = bp_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = bp_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = bp_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "BP_TERMINAL").replace(
        "AR_NINE", "BP_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

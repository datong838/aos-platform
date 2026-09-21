#!/usr/bin/env python3
"""Retire CD's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_cd_replacement_recovery as cd_replacement
import a0v_cd_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-cd"
retirement.AR_ID = successor.CD_ID
retirement.GENERATION = successor.CD_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("3eae682d-fddb-4b3b-a7b0-da0eb91152d2", 4, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-cd-retirement-20260921-v1"
retirement.DEFINITION_REVISION = 157
retirement.ACTIVE_ROUTE_REVISION = 213
retirement.ACTIVE_GROUP_REVISION = 240
retirement.DETACHED_ROUTE_REVISION = 215
retirement.DETACHED_GROUP_REVISION = 242


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = cd_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = cd_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = cd_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "CD_TERMINAL").replace(
        "AR_NINE", "CD_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

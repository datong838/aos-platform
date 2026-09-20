#!/usr/bin/env python3
"""Retire BU's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_bu_replacement_recovery as bu_replacement
import a0v_bu_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-bu"
retirement.AR_ID = successor.BU_ID
retirement.GENERATION = successor.BU_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("617da078-f4ef-4ad9-9ac6-bd764468fa67", 4, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-bu-retirement-20260920-v1"
retirement.DEFINITION_REVISION = 130
retirement.ACTIVE_ROUTE_REVISION = 186
retirement.ACTIVE_GROUP_REVISION = 213
retirement.DETACHED_ROUTE_REVISION = 188
retirement.DETACHED_GROUP_REVISION = 215


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = bu_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = bu_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = bu_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "BU_TERMINAL").replace(
        "AR_NINE", "BU_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

#!/usr/bin/env python3
"""Retire CE's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_ce_replacement_recovery as ce_replacement
import a0v_ce_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-ce"
retirement.AR_ID = successor.CE_ID
retirement.GENERATION = successor.CE_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("c1b948a7-faf2-4b92-8e8d-1f9d66b51201", 4, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-ce-retirement-20260921-v1"
retirement.DEFINITION_REVISION = 160
retirement.ACTIVE_ROUTE_REVISION = 216
retirement.ACTIVE_GROUP_REVISION = 243
retirement.DETACHED_ROUTE_REVISION = 218
retirement.DETACHED_GROUP_REVISION = 245


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = ce_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = ce_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = ce_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "CE_TERMINAL").replace(
        "AR_NINE", "CE_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

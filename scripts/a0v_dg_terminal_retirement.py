#!/usr/bin/env python3
"""Retire DG's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_dg_replacement_recovery as dg_replacement
import a0v_dg_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-dg"
retirement.AR_ID = successor.DG_ID
retirement.GENERATION = successor.DG_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("6e9e2fc8-d598-4e61-a6f0-d265ef7bceed", 4, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-dg-retirement-20260922-v1"
retirement.DEFINITION_REVISION = 241
retirement.ACTIVE_ROUTE_REVISION = 300
retirement.ACTIVE_GROUP_REVISION = 327
retirement.DETACHED_ROUTE_REVISION = 302
retirement.DETACHED_GROUP_REVISION = 329


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = dg_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = dg_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = dg_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "DG_TERMINAL").replace(
        "AR_NINE", "DG_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

#!/usr/bin/env python3
"""Retire DH's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_dh_replacement_recovery as dh_replacement
import a0v_dh_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-dh"
retirement.AR_ID = successor.DH_ID
retirement.GENERATION = successor.DH_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("40429d74-6faf-4895-8b2a-b0cc69df35a3", 4, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-dh-retirement-20260922-v1"
retirement.DEFINITION_REVISION = 244
retirement.ACTIVE_ROUTE_REVISION = 303
retirement.ACTIVE_GROUP_REVISION = 330
retirement.DETACHED_ROUTE_REVISION = 305
retirement.DETACHED_GROUP_REVISION = 332


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = dh_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = dh_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = dh_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "DH_TERMINAL").replace(
        "AR_NINE", "DH_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

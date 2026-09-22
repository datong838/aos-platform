#!/usr/bin/env python3
"""Retire DJ's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_dj_replacement_recovery as dj_replacement
import a0v_dj_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-dj"
retirement.AR_ID = successor.DJ_ID
retirement.GENERATION = successor.DJ_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("8bf657a8-2f62-4057-b2f9-352b64a28a6c", 4, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-dj-retirement-20260922-v1"
retirement.DEFINITION_REVISION = 250
retirement.ACTIVE_ROUTE_REVISION = 309
retirement.ACTIVE_GROUP_REVISION = 336
retirement.DETACHED_ROUTE_REVISION = 311
retirement.DETACHED_GROUP_REVISION = 338


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = dj_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = dj_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = dj_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "DJ_TERMINAL").replace(
        "AR_NINE", "DJ_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

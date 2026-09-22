#!/usr/bin/env python3
"""Retire DE's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_de_replacement_recovery as de_replacement
import a0v_de_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-de"
retirement.AR_ID = successor.DE_ID
retirement.GENERATION = successor.DE_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("c8ff272f-9fd2-4b54-aef2-87df454e0251", 5, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-de-retirement-20260922-v1"
retirement.DEFINITION_REVISION = 235
retirement.ACTIVE_ROUTE_REVISION = 294
retirement.ACTIVE_GROUP_REVISION = 321
retirement.DETACHED_ROUTE_REVISION = 296
retirement.DETACHED_GROUP_REVISION = 323


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = de_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = de_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = de_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "DE_TERMINAL").replace(
        "AR_NINE", "DE_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

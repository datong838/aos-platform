#!/usr/bin/env python3
"""Retire DI's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_di_replacement_recovery as di_replacement
import a0v_di_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-di"
retirement.AR_ID = successor.DI_ID
retirement.GENERATION = successor.DI_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("d394a0fc-c82e-41c1-ba07-e56b480b3866", 4, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-di-retirement-20260922-v1"
retirement.DEFINITION_REVISION = 247
retirement.ACTIVE_ROUTE_REVISION = 306
retirement.ACTIVE_GROUP_REVISION = 333
retirement.DETACHED_ROUTE_REVISION = 308
retirement.DETACHED_GROUP_REVISION = 335


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = di_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = di_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = di_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "DI_TERMINAL").replace(
        "AR_NINE", "DI_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

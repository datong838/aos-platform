#!/usr/bin/env python3
"""Retire CS's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_cs_replacement_recovery as cs_replacement
import a0v_cs_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-cs"
retirement.AR_ID = successor.CS_ID
retirement.GENERATION = successor.CS_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("b7d12c25-6673-48b3-aaba-dc803edb9169", 5, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-cs-retirement-20260921-v1"
retirement.DEFINITION_REVISION = 199
retirement.ACTIVE_ROUTE_REVISION = 258
retirement.ACTIVE_GROUP_REVISION = 285
retirement.DETACHED_ROUTE_REVISION = 260
retirement.DETACHED_GROUP_REVISION = 287


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = cs_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = cs_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = cs_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "CS_TERMINAL").replace(
        "AR_NINE", "CS_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

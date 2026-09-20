#!/usr/bin/env python3
"""Retire BR's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_br_replacement_recovery as br_replacement
import a0v_br_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-br"
retirement.AR_ID = successor.BR_ID
retirement.GENERATION = successor.BR_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("256207c9-4bc4-4c89-b00f-146f58012011", 8, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-br-retirement-20260920-v1"
retirement.DEFINITION_REVISION = 127
retirement.ACTIVE_ROUTE_REVISION = 177
retirement.ACTIVE_GROUP_REVISION = 204
retirement.DETACHED_ROUTE_REVISION = 179
retirement.DETACHED_GROUP_REVISION = 206


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = br_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = br_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = br_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "BR_TERMINAL").replace(
        "AR_NINE", "BR_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

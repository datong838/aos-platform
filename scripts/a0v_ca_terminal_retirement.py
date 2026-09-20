#!/usr/bin/env python3
"""Retire CA's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_ca_replacement_recovery as ca_replacement
import a0v_ca_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-ca"
retirement.AR_ID = successor.CA_ID
retirement.GENERATION = successor.CA_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("4a3ca4e5-db9f-47a0-a283-2adf23d25e84", 4, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-ca-retirement-20260921-v1"
retirement.DEFINITION_REVISION = 148
retirement.ACTIVE_ROUTE_REVISION = 204
retirement.ACTIVE_GROUP_REVISION = 231
retirement.DETACHED_ROUTE_REVISION = 206
retirement.DETACHED_GROUP_REVISION = 233


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = ca_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = ca_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = ca_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "CA_TERMINAL").replace(
        "AR_NINE", "CA_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

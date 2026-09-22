#!/usr/bin/env python3
"""Retire DC's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_dc_replacement_recovery as dc_replacement
import a0v_dc_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-dc"
retirement.AR_ID = successor.DC_ID
retirement.GENERATION = successor.DC_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("6092d972-5734-44f1-abe4-56020afb2b4d", 4, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-dc-retirement-20260922-v1"
retirement.DEFINITION_REVISION = 229
retirement.ACTIVE_ROUTE_REVISION = 288
retirement.ACTIVE_GROUP_REVISION = 315
retirement.DETACHED_ROUTE_REVISION = 290
retirement.DETACHED_GROUP_REVISION = 317


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = dc_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = dc_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = dc_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "DC_TERMINAL").replace(
        "AR_NINE", "DC_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

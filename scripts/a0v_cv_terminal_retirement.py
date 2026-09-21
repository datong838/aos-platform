#!/usr/bin/env python3
"""Retire CV's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_cv_replacement_recovery as cv_replacement
import a0v_cv_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-cv"
retirement.AR_ID = successor.CV_ID
retirement.GENERATION = successor.CV_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("88c9a09f-e5f3-4c65-9f5c-dc35cc1252e6", 4, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-cv-retirement-20260921-v1"
retirement.DEFINITION_REVISION = 208
retirement.ACTIVE_ROUTE_REVISION = 267
retirement.ACTIVE_GROUP_REVISION = 294
retirement.DETACHED_ROUTE_REVISION = 269
retirement.DETACHED_GROUP_REVISION = 296


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = cv_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = cv_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = cv_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.setup = setup
retirement.profile = profile


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "CV_TERMINAL").replace(
        "AR_NINE", "CV_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))

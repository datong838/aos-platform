#!/usr/bin/env python3
"""Detach released BQ through the formal disable Owner; never revive its generation."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_bq_replacement_recovery as bq_replacement
import a0v_bq_successor_business as bq_successor


retirement.STATE = bq_replacement.replacement.STATE / "retire-bq"
retirement.AR_ID = bq_successor.BQ_ID
retirement.GENERATION = bq_successor.BQ_GENERATION
retirement.LOCK = bq_successor.LOCK
retirement.FAILED_ATTEMPTS = ()
retirement.PREFIX = "a0v-qyh-released-bq-retirement-20260920-v1"
retirement.DEFINITION_REVISION = 124
retirement.ACTIVE_ROUTE_REVISION = 174
retirement.ACTIVE_GROUP_REVISION = 201
retirement.DETACHED_ROUTE_REVISION = 176
retirement.DETACHED_GROUP_REVISION = 203


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = bq_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = bq_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = bq_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


def setup():
    return bq_successor.setup()


retirement.profile = profile
retirement.setup = setup


def run(action: str) -> dict:
    if action not in retirement.ACTIONS:
        raise ValueError("unsupported BQ retirement action")
    result = getattr(retirement, action.replace("-", "_"))()
    result = json.loads(json.dumps(result, default=str).replace("AR_", "BQ_"))
    output = retirement.STATE / f"{action}-result.json"
    if not output.exists():
        retirement.freeze(output, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, default=str, indent=2))

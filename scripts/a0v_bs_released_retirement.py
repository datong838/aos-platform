#!/usr/bin/env python3
"""Detach released BS through the formal disable Owner; never revive its generation."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_bs_replacement_recovery as bs_replacement
import a0v_bs_successor_business as bs_successor


retirement.STATE = bs_replacement.replacement.STATE / "retire-bs"
retirement.AR_ID = bs_successor.BS_ID
retirement.GENERATION = bs_successor.BS_GENERATION
retirement.LOCK = bs_successor.LOCK
retirement.FAILED_ATTEMPTS = ()
retirement.PREFIX = "a0v-qyh-released-bs-retirement-20260920-v1"
retirement.DEFINITION_REVISION = 127
retirement.ACTIVE_ROUTE_REVISION = 180
retirement.ACTIVE_GROUP_REVISION = 207
retirement.DETACHED_ROUTE_REVISION = 182
retirement.DETACHED_GROUP_REVISION = 209


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = bs_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = bs_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = bs_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


def setup():
    return bs_successor.setup()


retirement.profile = profile
retirement.setup = setup


def run(action: str) -> dict:
    if action not in retirement.ACTIONS:
        raise ValueError("unsupported BS retirement action")
    result = getattr(retirement, action.replace("-", "_"))()
    result = json.loads(json.dumps(result, default=str).replace("AR_", "BS_"))
    output = retirement.STATE / f"{action}-result.json"
    if not output.exists():
        retirement.freeze(output, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, default=str, indent=2))

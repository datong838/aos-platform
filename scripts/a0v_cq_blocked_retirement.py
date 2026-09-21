#!/usr/bin/env python3
"""Detach configuration-blocked CQ through the existing exact disable owner."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_as_failed_retirement as retirement
import a0v_cq_replacement_recovery as cq_replacement
import a0v_cq_successor_business as successor


ROOT = Path(__file__).resolve().parents[1]
retirement.STATE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/replacement-cr/retire-cq"
retirement.AS_ID = successor.CQ_ID
retirement.GENERATION = successor.CQ_GENERATION
retirement.LOCK = successor.LOCK
retirement.PREFIX = "a0v-qyh-blocked-cq-retirement-20260921-v1"
retirement.FAILED_ATTEMPTS = ()
retirement.INSTALLATION_LABEL = "CQ"
retirement.SUCCESSOR_MODULE = "a0v_cq_successor_business"
retirement.ACTIVE_BINDING_REVISION = 9
retirement.ACTIVE_EXECUTION_EPOCH = 5
retirement.ACTIVE_ROUTE_EXECUTION_EPOCH = 3
retirement.DETACHED_BINDING_REVISION = 11
retirement.DETACHED_EXECUTION_EPOCH = 6
retirement.DEFINITION_REVISION = 193
retirement.ACTIVE_ROUTE_REVISION = 252
retirement.ACTIVE_GROUP_REVISION = 279
retirement.DETACHED_ROUTE_REVISION = 254
retirement.DETACHED_GROUP_REVISION = 281


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = cq_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = cq_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = cq_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


retirement.profile = profile
retirement.setup = successor.setup


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(retirement.run(args.action), ensure_ascii=False, default=str, indent=2))

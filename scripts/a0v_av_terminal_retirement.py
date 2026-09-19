#!/usr/bin/env python3
"""Detach terminal AV through the existing audited Runtime disable Owner."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_aq_failed_retirement as retirement


ROOT = Path(__file__).resolve().parents[1]
retirement.STATE = ROOT.parent / ".aos-recovery-20260919/state/q-advisor-baseline/replacement-aw/retire-av"
retirement.AQ_ID = "5f01eda8-ca5f-4892-8510-385704ccddb2"
retirement.GENERATION = "17104053-f4c9-47e1-89b0-f3f353076dda"
retirement.LOCK = "sha256:9c4d67c428cb5f3e7bcb0e05dc553e87efa0c764683b7ab5ca4d5011336c5e47"
retirement.FAILED_ATTEMPTS = (
    ("42717b1a-1d3b-442d-9b18-683593e4bbbf", 61, "abandoned",
     "ATTEMPT_LEASE_EXPIRED", None),
)
retirement.PREFIX = "a0v-qyh-terminal-av-retirement-20260919-v1"
retirement.DEFINITION_REVISION = 76
retirement.ACTIVE_ROUTE_REVISION = 117
retirement.ACTIVE_GROUP_REVISION = 144
retirement.DETACHED_ROUTE_REVISION = 119
retirement.DETACHED_GROUP_REVISION = 146


def setup():
    import a0v_av_successor_business as current
    return current.setup()


retirement.setup = setup


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AQ_FAILED", "AV_TERMINAL").replace("AQ_NINE", "AV_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, default=str, indent=2))

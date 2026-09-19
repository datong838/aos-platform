#!/usr/bin/env python3
"""Detach terminal BC through the existing audited Runtime disable Owner."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_aq_failed_retirement as retirement


ROOT = Path(__file__).resolve().parents[1]
retirement.STATE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/replacement-bd/retire-bc"
retirement.AQ_ID = "3b895c30-34ca-4710-b978-02645d49c83a"
retirement.GENERATION = "31776dcd-e28f-4b6d-ae45-75fb0ab5a505"
retirement.LOCK = "sha256:c59c7f036bb2a5e2892e854a79d1baca5b6ca915a191e7376812de9de54106a6"
retirement.FAILED_ATTEMPTS = (
    ("3ab54352-408c-4aae-a150-fb23c64cd7b7", 61, "abandoned",
     "ATTEMPT_LEASE_EXPIRED", None),
)
retirement.PREFIX = "a0v-qyh-terminal-bc-retirement-20260920-v1"
retirement.DEFINITION_REVISION = 91
retirement.ACTIVE_ROUTE_REVISION = 135
retirement.ACTIVE_GROUP_REVISION = 162
retirement.DETACHED_ROUTE_REVISION = 137
retirement.DETACHED_GROUP_REVISION = 164


def setup():
    import a0v_bc_successor_business as current
    return current.setup()


retirement.setup = setup


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AQ_FAILED", "BC_TERMINAL").replace("AQ_NINE", "BC_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, default=str, indent=2))

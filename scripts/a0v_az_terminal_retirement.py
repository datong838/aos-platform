#!/usr/bin/env python3
"""Detach terminal AZ through the existing audited Runtime disable Owner."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_aq_failed_retirement as retirement


ROOT = Path(__file__).resolve().parents[1]
retirement.STATE = ROOT.parent / ".aos-recovery-20260919/state/q-advisor-baseline/replacement-ba/retire-az"
retirement.AQ_ID = "40eee6d9-fb03-4657-a83e-aeb38ec4aeeb"
retirement.GENERATION = "7b6befaa-2f92-4e62-85f9-0ca060ec4b90"
retirement.LOCK = "sha256:7826b7400df634c9ad5f538b7db24026fc8930ee4bf6627b5d13277b2fa6afc5"
retirement.FAILED_ATTEMPTS = (
    ("5505b051-79f8-47a7-b2e2-4ddfc0893eb1", 61, "failed",
     "RECOVERABLE_INGRESS_DEADLINE_EXCEEDED", "IngressJournalConflict"),
    ("af15b2e5-7c72-47f0-9e1d-79855a970fd6", 4, "abandoned",
     "ATTEMPT_LEASE_EXPIRED", None),
)
retirement.PREFIX = "a0v-qyh-terminal-az-retirement-20260919-v1"
retirement.DEFINITION_REVISION = 82
retirement.ACTIVE_ROUTE_REVISION = 126
retirement.ACTIVE_GROUP_REVISION = 153
retirement.DETACHED_ROUTE_REVISION = 128
retirement.DETACHED_GROUP_REVISION = 155


def setup():
    import a0v_az_successor_business as current
    return current.setup()


retirement.setup = setup


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AQ_FAILED", "AZ_TERMINAL").replace("AQ_NINE", "AZ_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, default=str, indent=2))

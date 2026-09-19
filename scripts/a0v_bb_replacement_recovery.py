#!/usr/bin/env python3
"""Create BB directly from the exact detached BA authority."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_av_replacement_recovery as replacement


ROOT = Path(__file__).resolve().parents[1]
replacement.STATE = ROOT.parent / ".aos-recovery-20260919/state/q-advisor-baseline/replacement-bb"
replacement.AV_DIR = replacement.STATE / "bb"
replacement.AU_ID = "9110f69b-bb31-4d17-98e8-6c5ed1d9234f"
replacement.AU_GENERATION = "197f5036-656a-4b58-a261-e93e2fffea18"
replacement.LOCK = "sha256:6fc165d534435f39488e59c47d615501c1b011beadb59a4a92ed1de76d769757"
replacement.AU_DISABLE_OPERATION = "4668c723-0acc-446a-9c0d-80118e2f380c"
replacement.AU_DETACH_RECEIPT = "707b4a88-2823-4368-81c6-5e5525c3ea48"
replacement.AU_DETACH_HASH = "sha256:f3df39ef131deb553919a66c8fe2d4056ef096a4537447472f300e2936a941b5"
replacement.PREFIX = "a0v-qyh-clean-bb-20260919"
replacement.PREDECESSOR_ROUTE_REVISION = 131
replacement.PREDECESSOR_GROUP_REVISION = 158
replacement.DEFINITION_REVISION = 85
replacement.PREDECESSOR_BINDING_REVISION = 8
replacement.PREDECESSOR_EXECUTION_EPOCH = 4
replacement.INSTALLATION_LABEL = "bb"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "BB_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=replacement.ACTIONS)
    args = parser.parse_args()
    output = replacement.STATE / f"{args.action}-result.json"
    if output.exists():
        raise ValueError(f"immutable {args.action} output exists")
    result = run(args.action)
    replacement.freeze(output, result)
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

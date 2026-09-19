#!/usr/bin/env python3
"""Create BC directly from the exact detached BB authority."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_av_replacement_recovery as replacement


ROOT = Path(__file__).resolve().parents[1]
replacement.STATE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/replacement-bc"
replacement.AV_DIR = replacement.STATE / "bc"
replacement.AU_ID = "09752ccf-d51a-44b7-a5bf-62b5ab8ec5d6"
replacement.AU_GENERATION = "099c4d17-47fb-4c07-9ef1-c627ca7b4239"
replacement.LOCK = "sha256:f5ae36a5e7db006f81b87af036c5e83b6a3ed7f0f714182b15b598cd9f03fe37"
replacement.AU_DISABLE_OPERATION = "5e1e9518-eaf1-4fc0-9d6c-30721e342c6a"
replacement.AU_DETACH_RECEIPT = "0dd16596-c66b-4390-b9dc-0504c1a822c7"
replacement.AU_DETACH_HASH = "sha256:023f817fd9c924b05ec59ce011451cef0364061956e8c156cadbc7dfcde73a6a"
replacement.PREFIX = "a0v-qyh-clean-bc-20260920"
replacement.PREDECESSOR_ROUTE_REVISION = 134
replacement.PREDECESSOR_GROUP_REVISION = 161
replacement.DEFINITION_REVISION = 88
replacement.PREDECESSOR_BINDING_REVISION = 8
replacement.PREDECESSOR_EXECUTION_EPOCH = 4
replacement.INSTALLATION_LABEL = "bc"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "BC_")}


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

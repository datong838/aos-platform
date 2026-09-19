#!/usr/bin/env python3
"""Create BF directly from the exact detached BE authority."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_av_replacement_recovery as replacement


ROOT = Path(__file__).resolve().parents[1]
replacement.STATE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/replacement-bf"
replacement.AV_DIR = replacement.STATE / "bf"
replacement.AU_ID = "1a0f801f-d8f3-43af-a31e-5c9fc8161d6d"
replacement.AU_GENERATION = "93349d9b-ad61-4919-9cbd-e1e9b02545bb"
replacement.LOCK = "sha256:30602cd6e4b4adebd8b1710abc6cd5204284ab62d12598fde4fa527a72b8e05d"
replacement.AU_DISABLE_OPERATION = "dbe83c13-de44-4f49-8834-c6ac0a662782"
replacement.AU_DETACH_RECEIPT = "2b758ca2-8afd-48a4-af23-6367fe505758"
replacement.AU_DETACH_HASH = "sha256:db4450919ba39f8443aa20eb0a8b0d9be27eda5a17c40a069b17a0637e91651d"
replacement.PREFIX = "a0v-qyh-clean-bf-20260920"
replacement.PREDECESSOR_ROUTE_REVISION = 143
replacement.PREDECESSOR_GROUP_REVISION = 170
replacement.DEFINITION_REVISION = 97
replacement.PREDECESSOR_BINDING_REVISION = 8
replacement.PREDECESSOR_EXECUTION_EPOCH = 4
replacement.INSTALLATION_LABEL = "bf"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "BF_")}


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

#!/usr/bin/env python3
"""Create BP directly from the exact detached BO authority."""
from __future__ import annotations

import argparse
import json

import a0v_bo_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-bp"
replacement.AV_DIR = replacement.STATE / "bp"
replacement.AU_ID = "307399a0-21bb-4d55-95b2-8b0fee238913"
replacement.AU_GENERATION = "030bf59c-c998-4ee6-aedb-11d8d7d5831a"
replacement.LOCK = "sha256:0e6dc143f25c8dc043b30b324719cce42c37dcb7bde08b51b0add161a70c860f"
replacement.AU_DISABLE_OPERATION = "70cb9fec-1a8c-477c-bbdf-8134931ff3f6"
replacement.AU_DETACH_RECEIPT = "01853eba-d3d7-4e2a-a5c5-a6c346e1679c"
replacement.AU_DETACH_HASH = "sha256:dfc96a07480ea85f910260822b97536a6569154966dfc2e2db855f7860ac48d1"
replacement.PREFIX = "a0v-qyh-clean-bp-20260920"
replacement.PREDECESSOR_ROUTE_REVISION = 170
replacement.PREDECESSOR_GROUP_REVISION = 197
replacement.DEFINITION_REVISION = 121
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "bp"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "BP_")}


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

#!/usr/bin/env python3
"""Create BZ directly from the exact detached BY authority."""
from __future__ import annotations

import argparse
import json

import a0v_by_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-bz"
replacement.AV_DIR = replacement.STATE / "bz"
replacement.AU_ID = "ed64db1a-45eb-442e-8f1b-49ed899731dc"
replacement.AU_GENERATION = "01f99334-0515-4c73-b442-a293709b3cc2"
replacement.LOCK = "sha256:77165c48df63d332cebf02dfa35f59711d7d1af5dc5f396db86c23400f3653cc"
replacement.AU_DISABLE_OPERATION = "53104614-eeaf-4c87-a5fa-97f0e518f207"
replacement.AU_DETACH_RECEIPT = "476431d3-9cb4-4e5f-bd4b-02ac2c9fd978"
replacement.AU_DETACH_HASH = "sha256:d65a5f35ed1e32e2db5e71e93e2a201eff195fe8e0ce6a859cceee468da3dbcb"
replacement.PREFIX = "a0v-qyh-clean-bz-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 200
replacement.PREDECESSOR_GROUP_REVISION = 227
replacement.DEFINITION_REVISION = 142
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "bz"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "BZ_")}


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

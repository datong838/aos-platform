#!/usr/bin/env python3
"""Create DC directly from the exact detached DB authority."""
from __future__ import annotations

import argparse
import json

import a0v_db_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-dc"
replacement.AV_DIR = replacement.STATE / "dc"
replacement.AU_ID = "aaaa1ac1-2c35-4c35-8e7b-3ed6cd47f9c8"
replacement.AU_GENERATION = "c1ae6205-0743-483c-82e3-1d1c95b1ab31"
replacement.LOCK = "sha256:f277f3d8cba10eb9beb19b18e21f37814a485e271f09ce36c6005dc3723c5484"
replacement.AU_DISABLE_OPERATION = "d10cce0c-d412-4e29-95a4-68c010cb2522"
replacement.AU_DETACH_RECEIPT = "eceafbf4-d492-43d5-b036-d49e054de133"
replacement.AU_DETACH_HASH = "sha256:4a74a25a361e745a41bddde502105c030399a716d2f5f6f9ed5f01fa36c4aa54"
replacement.PREFIX = "a0v-qyh-clean-dc-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 287
replacement.PREDECESSOR_GROUP_REVISION = 314
replacement.DEFINITION_REVISION = 226
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "dc"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "DC_").replace("DB_", "DC_")}


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

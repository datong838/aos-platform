#!/usr/bin/env python3
"""Create CD directly from the exact detached CC authority."""
from __future__ import annotations

import argparse
import json

import a0v_cc_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-cd"
replacement.AV_DIR = replacement.STATE / "cd"
replacement.AU_ID = "03942567-0f78-4530-b9dd-634bec59c780"
replacement.AU_GENERATION = "c1ffee4f-c13b-4d1a-93d2-c3b35bd66ca2"
replacement.LOCK = "sha256:e90cdcbf95f12f2edcc711c51e55c67ad938364d894c40f0cf33d7f41313010b"
replacement.AU_DISABLE_OPERATION = "9cf43145-2578-4815-9d14-7ac7430c6327"
replacement.AU_DETACH_RECEIPT = "af7f0b34-1279-4ca7-972b-ef0e31fd53b3"
replacement.AU_DETACH_HASH = "sha256:848870b0fd047ebf70beb0361ba99e9e4b72375138d66b2df8aeda9ee6c11ea3"
replacement.PREFIX = "a0v-qyh-clean-cd-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 212
replacement.PREDECESSOR_GROUP_REVISION = 239
replacement.DEFINITION_REVISION = 154
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "cd"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "CD_")}


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

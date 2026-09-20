#!/usr/bin/env python3
"""Create BY directly from the exact detached BX authority."""
from __future__ import annotations

import argparse
import json

import a0v_bx_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-by"
replacement.AV_DIR = replacement.STATE / "by"
replacement.AU_ID = "45db7b1e-6463-40f2-bf3c-c4e64ce3fd78"
replacement.AU_GENERATION = "9beb5c99-aba7-4bec-9a10-4f98415aed2f"
replacement.LOCK = "sha256:b4af00ba55283a22a08b1b045a3adc647854313856ebfd960bccff70f5a15152"
replacement.AU_DISABLE_OPERATION = "05d32449-7543-4136-afec-9ce7c78c7365"
replacement.AU_DETACH_RECEIPT = "608d36a3-198b-46e2-bc5b-d653e44d44c8"
replacement.AU_DETACH_HASH = "sha256:1862820a36540eb75b301673e8c5e4553cd1c2f05facf602a35dda4c20754e9c"
replacement.PREFIX = "a0v-qyh-clean-by-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 197
replacement.PREDECESSOR_GROUP_REVISION = 224
replacement.DEFINITION_REVISION = 139
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "by"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "BY_")}


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

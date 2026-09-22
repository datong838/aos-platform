#!/usr/bin/env python3
"""Create DE directly from the exact detached DD authority."""
from __future__ import annotations

import argparse
import json

import a0v_dd_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-de"
replacement.AV_DIR = replacement.STATE / "de"
replacement.AU_ID = "6e05658b-5d0a-40ae-ab8e-81fcca5269db"
replacement.AU_GENERATION = "422d2d5b-752a-4182-b1e8-831a8f63c2a1"
replacement.LOCK = "sha256:9d83e86209865176f599127f34a38887e21715ac6095a75e963515dca96c5ea4"
replacement.AU_DISABLE_OPERATION = "8e227c68-9a74-4951-827f-acfef75a948b"
replacement.AU_DETACH_RECEIPT = "5211f8d4-e02a-4d06-b806-c1c5144505e8"
replacement.AU_DETACH_HASH = "sha256:ca77ede8b7156b5dc8a3c0de3598c0807a4cfb06719c94039c444a526eb58f16"
replacement.PREFIX = "a0v-qyh-clean-de-20260922"
replacement.PREDECESSOR_ROUTE_REVISION = 293
replacement.PREDECESSOR_GROUP_REVISION = 320
replacement.DEFINITION_REVISION = 232
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "de"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "DE_").replace("DD_", "DE_")}


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

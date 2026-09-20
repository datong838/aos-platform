#!/usr/bin/env python3
"""Create BU directly from the exact detached BT authority."""
from __future__ import annotations

import argparse
import json

import a0v_bt_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-bu"
replacement.AV_DIR = replacement.STATE / "bu"
replacement.AU_ID = "b05b7f06-67a0-4ea1-bc7c-1ba2108653d5"
replacement.AU_GENERATION = "2c2d4cd5-d9bd-45b4-86d9-72a979eb0a58"
replacement.LOCK = "sha256:053ba1e22ac7ddb9a0ff227643fe3bda76d37d8cc38e808df351954614edb974"
replacement.AU_DISABLE_OPERATION = "84699050-9e0a-48b7-8dc3-99e2d7dbc669"
replacement.AU_DETACH_RECEIPT = "3c4c44d3-7f5f-4829-951a-5ba5c4c37aaa"
replacement.AU_DETACH_HASH = "sha256:49271deaba3745fe1f75f7e041b058f285f6706364cda4d8afddb0315b9c5528"
replacement.PREFIX = "a0v-qyh-clean-bu-20260920"
replacement.PREDECESSOR_ROUTE_REVISION = 185
replacement.PREDECESSOR_GROUP_REVISION = 212
replacement.DEFINITION_REVISION = 127
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "bu"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "BU_")}


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

#!/usr/bin/env python3
"""Create BV directly from the exact detached BU authority."""
from __future__ import annotations

import argparse
import json

import a0v_bu_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-bv"
replacement.AV_DIR = replacement.STATE / "bv"
replacement.AU_ID = "d1dcf5c2-f6ff-48b2-b6f1-fb05d17b7895"
replacement.AU_GENERATION = "cb8ace71-ba8d-4e08-816b-8d6bbc0f0281"
replacement.LOCK = "sha256:470af8d75bc784496260df85be7953537f2d2ead135167dc2d14f16e9bc1d2ed"
replacement.AU_DISABLE_OPERATION = "55fab898-08ac-4548-9f07-a3e1a40485e9"
replacement.AU_DETACH_RECEIPT = "b071b45a-1e66-4898-b79c-49f1fdcd69ea"
replacement.AU_DETACH_HASH = "sha256:1eba5bd30d384de6ab165e9a617c7963fda5216775506d0341adfd1b63488163"
replacement.PREFIX = "a0v-qyh-clean-bv-20260920"
replacement.PREDECESSOR_ROUTE_REVISION = 188
replacement.PREDECESSOR_GROUP_REVISION = 215
replacement.DEFINITION_REVISION = 130
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "bv"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "BV_")}


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

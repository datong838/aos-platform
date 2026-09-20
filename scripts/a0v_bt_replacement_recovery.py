#!/usr/bin/env python3
"""Create BT directly from the exact detached BS authority."""
from __future__ import annotations

import argparse
import json

import a0v_bs_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-bt"
replacement.AV_DIR = replacement.STATE / "bt"
replacement.AU_ID = "c5a95204-c379-4763-b697-b4417349d204"
replacement.AU_GENERATION = "6f8bcb56-5717-4d7a-9a9e-97c1982db053"
replacement.LOCK = "sha256:0a3e5483351102d624ea389fafc865266c3ad642c70466068146705d4507c6ec"
replacement.AU_DISABLE_OPERATION = "0d5bbaa8-b5b4-4e12-b4cd-13b9ac00669f"
replacement.AU_DETACH_RECEIPT = "ddd1e074-b90d-411e-93a3-0595d6e86d8b"
replacement.AU_DETACH_HASH = "sha256:2995a8a4d8d2a74ddbde34a521de984af0afad13844303f6883befe48fe58242"
replacement.PREFIX = "a0v-qyh-clean-bt-20260920"
replacement.PREDECESSOR_ROUTE_REVISION = 182
replacement.PREDECESSOR_GROUP_REVISION = 209
replacement.DEFINITION_REVISION = 127
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "bt"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "BT_")}


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

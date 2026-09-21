#!/usr/bin/env python3
"""Create CN directly from the exact detached CM authority."""
from __future__ import annotations

import argparse
import json

import a0v_cm_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-cn"
replacement.AV_DIR = replacement.STATE / "cn"
replacement.AU_ID = "b52c8e1c-a343-4ef4-b106-38d859ba9677"
replacement.AU_GENERATION = "d3ec88cc-a05a-4895-bc27-c983a367a9a8"
replacement.LOCK = "sha256:50f9a34602014a44de489eb978c6684706aeff1435733684b2262133fce553ab"
replacement.AU_DISABLE_OPERATION = "cc32921f-27a2-43a0-94e4-23b84992e278"
replacement.AU_DETACH_RECEIPT = "a118ae49-92de-477a-92f3-0d855c48a472"
replacement.AU_DETACH_HASH = "sha256:5074648fad39e4be7040cac99fc18cc0748a6d162e2700ea0d78aa19c80803af"
replacement.PREFIX = "a0v-qyh-clean-cn-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 242
replacement.PREDECESSOR_GROUP_REVISION = 269
replacement.DEFINITION_REVISION = 184
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "cn"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "CN_")}


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

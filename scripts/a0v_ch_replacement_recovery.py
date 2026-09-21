#!/usr/bin/env python3
"""Create CH directly from the exact detached CG authority."""
from __future__ import annotations

import argparse
import json

import a0v_cg_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-ch"
replacement.AV_DIR = replacement.STATE / "ch"
replacement.AU_ID = "8f42819c-0fc7-48cf-a5c4-9ba96894a6f5"
replacement.AU_GENERATION = "3ed300fa-5fff-4949-9fb0-1926412e51ae"
replacement.LOCK = "sha256:554edd86332cff3f2879d4167f2ae7b16f4836af736dd3ff2545b66a57a3438d"
replacement.AU_DISABLE_OPERATION = "bd5e0164-fefb-4751-a7bd-5019a20dd3b5"
replacement.AU_DETACH_RECEIPT = "3d65b065-8ad4-4a97-983f-f14ca0ada8cb"
replacement.AU_DETACH_HASH = "sha256:bbf8fb158183e1821129384611658468d0a6d28838068c6ad45960b2b36dc025"
replacement.PREFIX = "a0v-qyh-clean-ch-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 224
replacement.PREDECESSOR_GROUP_REVISION = 251
replacement.DEFINITION_REVISION = 166
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "ch"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "CH_")}


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

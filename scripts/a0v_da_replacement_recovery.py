#!/usr/bin/env python3
"""Create DA directly from the exact detached CZ authority."""
from __future__ import annotations

import argparse
import json

import a0v_cz_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-da"
replacement.AV_DIR = replacement.STATE / "da"
replacement.AU_ID = "162e4c29-a24e-4c6b-8da7-9582d090d708"
replacement.AU_GENERATION = "d1b0f7eb-9677-4d52-a656-a4ae28942976"
replacement.LOCK = "sha256:b7045d4fb19c9f0482ac08a12cae8276c4878b3cb2290bd3f4ade0b5b7f885e6"
replacement.AU_DISABLE_OPERATION = "00211d70-345e-4f90-8d06-81a9a19a4436"
replacement.AU_DETACH_RECEIPT = "211b6762-550a-475f-aab6-9f6086786787"
replacement.AU_DETACH_HASH = "sha256:de79f4af293f2a159d0ac76ef47392761946cf2fb6d7203b8e89143e2b4b65b7"
replacement.PREFIX = "a0v-qyh-clean-da-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 281
replacement.PREDECESSOR_GROUP_REVISION = 308
replacement.DEFINITION_REVISION = 220
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "da"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "DA_").replace("CZ_", "DA_")}


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

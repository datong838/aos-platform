#!/usr/bin/env python3
"""Create CE directly from the exact detached CD authority."""
from __future__ import annotations

import argparse
import json

import a0v_cd_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-ce"
replacement.AV_DIR = replacement.STATE / "ce"
replacement.AU_ID = "01b41c17-fce2-4bcf-8d9e-a48d2d4bf743"
replacement.AU_GENERATION = "22639b06-1211-424d-9f64-696822e0add4"
replacement.LOCK = "sha256:3c38e9de616a063e451e53f23d0cf5ba08101a7ba0854904107fd5d3293ab65a"
replacement.AU_DISABLE_OPERATION = "858ed397-2cc6-40dd-b312-3faf129cb0c1"
replacement.AU_DETACH_RECEIPT = "b1d1dc98-268c-484c-a0f6-25502b4e8193"
replacement.AU_DETACH_HASH = "sha256:5f250085b837c6e59cba62e55de38e59785dc06a3ec63c384158aec9148df75d"
replacement.PREFIX = "a0v-qyh-clean-ce-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 215
replacement.PREDECESSOR_GROUP_REVISION = 242
replacement.DEFINITION_REVISION = 157
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "ce"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "CE_")}


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

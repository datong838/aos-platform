#!/usr/bin/env python3
"""Create CY directly from the exact detached CX authority."""
from __future__ import annotations

import argparse
import json

import a0v_cx_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-cy"
replacement.AV_DIR = replacement.STATE / "cy"
replacement.AU_ID = "2e374e12-7523-466d-aed7-bdabe8b69aff"
replacement.AU_GENERATION = "222870ba-ad3c-4cf5-a6de-e1b3a52ab5bc"
replacement.LOCK = "sha256:479419d261424399c29cac763588440b6ad4981b42bdf67b2a1615d16e715ccc"
replacement.AU_DISABLE_OPERATION = "1a1bcf55-b7a9-4869-ac48-052919593d57"
replacement.AU_DETACH_RECEIPT = "7753b075-1795-4435-a49c-1fb9f609f8f9"
replacement.AU_DETACH_HASH = "sha256:21a1c832c8b2b6c462db82efda362a311fb1980402bea9da441156d8fdca5c0c"
replacement.PREFIX = "a0v-qyh-clean-cy-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 275
replacement.PREDECESSOR_GROUP_REVISION = 302
replacement.DEFINITION_REVISION = 214
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "cy"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "CY_").replace("CX_", "CY_")}


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

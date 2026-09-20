#!/usr/bin/env python3
"""Create BX directly from the exact detached BW authority."""
from __future__ import annotations

import argparse
import json

import a0v_bw_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-bx"
replacement.AV_DIR = replacement.STATE / "bx"
replacement.AU_ID = "9b6e1277-a0a2-447d-9062-a98adfed3f22"
replacement.AU_GENERATION = "62cf014b-9ce5-4512-8a34-b55a79e053c3"
replacement.LOCK = "sha256:5b2392496ba942a535260209dcf681030dd00b58765bf4983622d4af0be49ee0"
replacement.AU_DISABLE_OPERATION = "08730e81-28b4-4931-9670-9056259a69ff"
replacement.AU_DETACH_RECEIPT = "d3ca6ecb-5fea-4dda-8a30-3ac9f5ce047c"
replacement.AU_DETACH_HASH = "sha256:e1365bbc1f87d42997df4c04b5167d75895de232e69f81f9412e4ffaf9cebb5e"
replacement.PREFIX = "a0v-qyh-clean-bx-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 194
replacement.PREDECESSOR_GROUP_REVISION = 221
replacement.DEFINITION_REVISION = 136
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "bx"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "BX_")}


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

#!/usr/bin/env python3
"""Create CF directly from the exact detached CE authority."""
from __future__ import annotations

import argparse
import json

import a0v_ce_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-cf"
replacement.AV_DIR = replacement.STATE / "cf"
replacement.AU_ID = "29d1b06d-3baa-4476-9cf8-5ea345d134c7"
replacement.AU_GENERATION = "e51d0010-d57f-4f5c-8f7e-7a1d732bebf7"
replacement.LOCK = "sha256:4fce233072671887c694e6c0b6c44080cf67e60407f7a1545b3dc4ef2aac9eb9"
replacement.AU_DISABLE_OPERATION = "077d774d-7614-4270-ad29-7f90871c3e9f"
replacement.AU_DETACH_RECEIPT = "d626046d-ceae-402e-8fbe-51ebe87b1409"
replacement.AU_DETACH_HASH = "sha256:ffa929f43cc570edf7029abec398fe03c52cd06b4d3fd8fdb7a0a7fd5ede3981"
replacement.PREFIX = "a0v-qyh-clean-cf-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 218
replacement.PREDECESSOR_GROUP_REVISION = 245
replacement.DEFINITION_REVISION = 160
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "cf"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "CF_")}


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

#!/usr/bin/env python3
"""Create BW directly from the exact detached BV authority."""
from __future__ import annotations

import argparse
import json

import a0v_bv_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-bw"
replacement.AV_DIR = replacement.STATE / "bw"
replacement.AU_ID = "2b1aa826-b595-40d4-aeb2-9a7ce9d33c36"
replacement.AU_GENERATION = "e8a5b32b-9a29-41bf-9c7f-87c7cd96b359"
replacement.LOCK = "sha256:5b994767e0abd7c6138b611e96dae1948ff1812dd02aeb23ad38b229280eb73f"
replacement.AU_DISABLE_OPERATION = "abea8903-916f-4d60-ba24-3453aeb4e8a9"
replacement.AU_DETACH_RECEIPT = "76145710-3ec6-4271-a8b7-248e045645f7"
replacement.AU_DETACH_HASH = "sha256:dc20911dba0fe1792b1a881f215109d8bf6f4db2754bdf12d3cc3fdab0e58608"
replacement.PREFIX = "a0v-qyh-clean-bw-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 191
replacement.PREDECESSOR_GROUP_REVISION = 218
replacement.DEFINITION_REVISION = 133
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "bw"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "BW_")}


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

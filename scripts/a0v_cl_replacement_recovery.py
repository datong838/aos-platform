#!/usr/bin/env python3
"""Create CL directly from the exact detached CK authority."""
from __future__ import annotations

import argparse
import json

import a0v_ck_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-cl"
replacement.AV_DIR = replacement.STATE / "cl"
replacement.AU_ID = "c1cb44ba-68ae-4d32-9974-5f031554fed2"
replacement.AU_GENERATION = "1edb1688-e2b6-42f0-b513-849ae372859e"
replacement.LOCK = "sha256:e7b527f80ede65ef8aeade78c0ea29a0199e6986f557e135c547521c4f637e4c"
replacement.AU_DISABLE_OPERATION = "87aa9a73-329e-42df-ac89-0e24bd8e4780"
replacement.AU_DETACH_RECEIPT = "8ed70360-4e39-4a96-992f-d70f3222b541"
replacement.AU_DETACH_HASH = "sha256:812e9450e64a730d13b34db809903cbd61d3c537c4bc4fb3ba06eb09aaa15144"
replacement.PREFIX = "a0v-qyh-clean-cl-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 236
replacement.PREDECESSOR_GROUP_REVISION = 263
replacement.DEFINITION_REVISION = 178
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "cl"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "CL_")}


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

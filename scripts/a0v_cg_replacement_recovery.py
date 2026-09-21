#!/usr/bin/env python3
"""Create CG directly from the exact detached CF authority."""
from __future__ import annotations

import argparse
import json

import a0v_cf_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-cg"
replacement.AV_DIR = replacement.STATE / "cg"
replacement.AU_ID = "8cf0c597-cf81-4fa5-b1ff-f27e3537a94c"
replacement.AU_GENERATION = "88996259-ad79-4aa6-962c-c29a24559db8"
replacement.LOCK = "sha256:672e44b9964c3d284028abd6af01fdbc6e2eeb81fa732e68a88061d28331a214"
replacement.AU_DISABLE_OPERATION = "0858ea02-0d34-49dc-b2c4-4276b31c72b7"
replacement.AU_DETACH_RECEIPT = "829cd86a-bf4e-4b62-a0e8-e3a89c34b9e0"
replacement.AU_DETACH_HASH = "sha256:0f2adfef50c42ed684a0ccdedf737a9a13a9e31b55d7b778b08f3f49e1bb2f6b"
replacement.PREFIX = "a0v-qyh-clean-cg-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 221
replacement.PREDECESSOR_GROUP_REVISION = 248
replacement.DEFINITION_REVISION = 163
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "cg"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "CG_")}


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

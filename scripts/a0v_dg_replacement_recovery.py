#!/usr/bin/env python3
"""Create DG directly from the exact detached DF authority."""
from __future__ import annotations

import argparse
import json

import a0v_df_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-dg"
replacement.AV_DIR = replacement.STATE / "dg"
replacement.AU_ID = "a0639f78-af04-4249-97f6-d8507de45f44"
replacement.AU_GENERATION = "ec18c8c6-2694-44c1-a9c9-ea79ea606e45"
replacement.LOCK = "sha256:42e81bdde355a2e2578ed4aebfb0302ad47584c614bc6f8a1e92495a8be61988"
replacement.AU_DISABLE_OPERATION = "06664a6c-c6da-4ecd-80e7-87b0b1ade018"
replacement.AU_DETACH_RECEIPT = "6c1dbb1e-6aec-4276-97fd-5bf7ee90ae03"
replacement.AU_DETACH_HASH = "sha256:a7cecfce6cd17074fcff0ce9feec405d5d95eaf1a117466b2a4b5db7f3f51330"
replacement.PREFIX = "a0v-qyh-clean-dg-20260922"
replacement.PREDECESSOR_ROUTE_REVISION = 299
replacement.PREDECESSOR_GROUP_REVISION = 326
replacement.DEFINITION_REVISION = 238
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "dg"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "DG_").replace("DF_", "DG_")}


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

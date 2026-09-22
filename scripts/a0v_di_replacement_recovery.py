#!/usr/bin/env python3
"""Create DI directly from the exact detached DH authority."""
from __future__ import annotations

import argparse
import json

import a0v_dh_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-di"
replacement.AV_DIR = replacement.STATE / "di"
replacement.AU_ID = "10d583ad-96ee-4b1a-bb18-92e428abe16e"
replacement.AU_GENERATION = "107a24f5-691d-4f2a-9b46-4e7b21938146"
replacement.LOCK = "sha256:aad5193620d1517a9b3be224440004eb040ad4b439d057ea0291ff0724d5d334"
replacement.AU_DISABLE_OPERATION = "c1750709-45a0-4c1a-ad89-63de6f2ca3e4"
replacement.AU_DETACH_RECEIPT = "6a8a6daa-1c32-45af-89f4-3bb2cf7ac80c"
replacement.AU_DETACH_HASH = "sha256:505640a22de3ee4b9cec5c9de036c7d3ff05e55bb2472f9d1bdadc5150220ea3"
replacement.PREFIX = "a0v-qyh-clean-di-20260922"
replacement.PREDECESSOR_ROUTE_REVISION = 305
replacement.PREDECESSOR_GROUP_REVISION = 332
replacement.DEFINITION_REVISION = 244
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "di"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "DI_").replace("DH_", "DI_")}


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

#!/usr/bin/env python3
"""Create DB directly from the exact detached DA authority."""
from __future__ import annotations

import argparse
import json

import a0v_da_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-db"
replacement.AV_DIR = replacement.STATE / "db"
replacement.AU_ID = "f4fcdf0b-a37b-419c-9de0-14b08cd7320d"
replacement.AU_GENERATION = "dbcdd8cb-c6f4-47cc-91f9-1662f54044c0"
replacement.LOCK = "sha256:47e3295d76f176a553f224b23e550b403be071c96b078d0c0410cd2117b3b38e"
replacement.AU_DISABLE_OPERATION = "d8d173ad-6d54-4002-b844-003fabf41b69"
replacement.AU_DETACH_RECEIPT = "4285f549-aa8f-4d98-b370-ed2cdf040381"
replacement.AU_DETACH_HASH = "sha256:bf47d2487469ca9eb6092a68dd5ad980ace527d58615490dac59f4f8292b5ab7"
replacement.PREFIX = "a0v-qyh-clean-db-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 284
replacement.PREDECESSOR_GROUP_REVISION = 311
replacement.DEFINITION_REVISION = 223
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "db"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "DB_").replace("DA_", "DB_")}


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

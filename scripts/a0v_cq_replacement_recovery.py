#!/usr/bin/env python3
"""Create CQ directly from the exact detached CP authority."""
from __future__ import annotations

import argparse
import json

import a0v_cp_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-cq"
replacement.AV_DIR = replacement.STATE / "cq"
replacement.AU_ID = "1d8b71c5-1cde-4d16-b16f-835f92bf8663"
replacement.AU_GENERATION = "9b0201fc-9822-4527-b63c-23cbd416057d"
replacement.LOCK = "sha256:9eb345e2ed64ed8ea82b997218fc6a029a05c342c3e3fba58d85e55b6acf857e"
replacement.AU_DISABLE_OPERATION = "fc24ee2f-52cb-40e8-98e0-dd260db335d2"
replacement.AU_DETACH_RECEIPT = "4603f48f-2d3a-4581-b837-b85658a2cf50"
replacement.AU_DETACH_HASH = "sha256:05a9ec8c3b477d23c0b329dded09c2d4ad08d686a2997fc36bb4bab46db95205"
replacement.PREFIX = "a0v-qyh-clean-cq-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 251
replacement.PREDECESSOR_GROUP_REVISION = 278
replacement.DEFINITION_REVISION = 193
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "cq"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "CQ_")}


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

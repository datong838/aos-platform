#!/usr/bin/env python3
"""Create CX directly from the exact detached CW authority."""
from __future__ import annotations

import argparse
import json

import a0v_cw_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-cx"
replacement.AV_DIR = replacement.STATE / "cx"
replacement.AU_ID = "0d5d5a7f-6e40-4725-b337-b79acc7d896a"
replacement.AU_GENERATION = "a60036f1-5887-4157-ad32-616925b547bf"
replacement.LOCK = "sha256:ed07dc19c26651fd6c845702f96f3a881642361f29d2f6495052a230d1fa0162"
replacement.AU_DISABLE_OPERATION = "e69aa8dc-45ab-4d4d-bb23-008fe3491524"
replacement.AU_DETACH_RECEIPT = "5aa372a9-1a82-41ff-b25e-00e898cda82a"
replacement.AU_DETACH_HASH = "sha256:2f121bf22c69efb2e4f37e1df1c17202c5c695e6a378459a92d07054108af78c"
replacement.PREFIX = "a0v-qyh-clean-cx-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 272
replacement.PREDECESSOR_GROUP_REVISION = 299
replacement.DEFINITION_REVISION = 211
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "cx"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "CX_").replace("CW_", "CX_")}


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

#!/usr/bin/env python3
"""Create CC directly from the exact detached CB authority."""
from __future__ import annotations

import argparse
import json

import a0v_cb_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-cc"
replacement.AV_DIR = replacement.STATE / "cc"
replacement.AU_ID = "3d6df614-5a05-4c6f-823e-688d81e84096"
replacement.AU_GENERATION = "0cceac8c-c831-4b3f-92c3-fc35240c5414"
replacement.LOCK = "sha256:658b48f2444dfd18c6c42bbbadd22a7952063c60b6bae95d7384c6841ab9d3f7"
replacement.AU_DISABLE_OPERATION = "6695a5a7-e5e6-4662-ad06-9495f9ed3e9a"
replacement.AU_DETACH_RECEIPT = "087eed56-f46c-4a9b-bc57-ba24e2e78d04"
replacement.AU_DETACH_HASH = "sha256:ab3661056826d5a9998c8ba55d278317429fcb9286b7efa65fca467c2615be49"
replacement.PREFIX = "a0v-qyh-clean-cc-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 209
replacement.PREDECESSOR_GROUP_REVISION = 236
replacement.DEFINITION_REVISION = 151
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "cc"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "CC_")}


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

#!/usr/bin/env python3
"""Create CW directly from the exact detached CV authority."""
from __future__ import annotations

import argparse
import json

import a0v_cv_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-cw"
replacement.AV_DIR = replacement.STATE / "cw"
replacement.AU_ID = "f94149ca-a01e-4a20-836f-3f5132e0dbb7"
replacement.AU_GENERATION = "82aec2b8-072d-4f2e-9624-f9539c8890a6"
replacement.LOCK = "sha256:9d8d72cdaad153c6e085ead8a3c28c4507fc226b421e0d60be8a100ac38318df"
replacement.AU_DISABLE_OPERATION = "17648f28-66dc-4c11-87d2-c32e3a016bcb"
replacement.AU_DETACH_RECEIPT = "9add3bab-81be-417d-ab80-18f254ecf43f"
replacement.AU_DETACH_HASH = "sha256:a8bc901472293b85f1b6085e97ea673dbe3ea79216668d6b6c15ffb6a0fb9bea"
replacement.PREFIX = "a0v-qyh-clean-cw-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 269
replacement.PREDECESSOR_GROUP_REVISION = 296
replacement.DEFINITION_REVISION = 208
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "cw"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "CW_").replace("CV_", "CW_")}


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

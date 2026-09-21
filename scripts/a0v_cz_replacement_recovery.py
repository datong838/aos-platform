#!/usr/bin/env python3
"""Create CZ directly from the exact detached CY authority."""
from __future__ import annotations

import argparse
import json

import a0v_cy_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-cz"
replacement.AV_DIR = replacement.STATE / "cz"
replacement.AU_ID = "917cd341-96a5-4428-9508-03c716c587ad"
replacement.AU_GENERATION = "a2fdbdb1-430c-417b-969d-6bd30874d38c"
replacement.LOCK = "sha256:8402d118a9ce1b12bbc4900144bc323634bd17e9a8b8af2e8de38cb9db637444"
replacement.AU_DISABLE_OPERATION = "40cd6259-298f-4aeb-96b1-3ef1cbe50d6e"
replacement.AU_DETACH_RECEIPT = "90718b50-d3c8-4712-91c7-41b6ab0358bf"
replacement.AU_DETACH_HASH = "sha256:932ac829528ff8fa7da0d05239f70eee127df1f7e34e7da4a9d6b44d20899b03"
replacement.PREFIX = "a0v-qyh-clean-cz-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 278
replacement.PREDECESSOR_GROUP_REVISION = 305
replacement.DEFINITION_REVISION = 217
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "cz"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "CZ_").replace("CY_", "CZ_")}


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

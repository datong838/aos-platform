#!/usr/bin/env python3
"""Create CT directly from the exact detached CS authority."""
from __future__ import annotations

import argparse
import json

import a0v_cs_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-ct"
replacement.AV_DIR = replacement.STATE / "ct"
replacement.AU_ID = "ff72acba-1e59-4da3-b92a-18737e18e9d2"
replacement.AU_GENERATION = "01a1719d-1109-440f-a233-1c5a6adb0d81"
replacement.LOCK = "sha256:1b37fab980943517deeec01b88f1ebe119b6143fc7db13c42ca9e4756e3af65a"
replacement.AU_DISABLE_OPERATION = "fa96b3bf-b140-466b-bb10-3a0d604dde1e"
replacement.AU_DETACH_RECEIPT = "13c4d61c-ea9b-4f13-94d7-12e21e8a09a4"
replacement.AU_DETACH_HASH = "sha256:f745d09717dbf72734a3792e67b2f9b88c692f23fe7c03fd903291bccfcb99a6"
replacement.PREFIX = "a0v-qyh-clean-ct-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 260
replacement.PREDECESSOR_GROUP_REVISION = 287
replacement.DEFINITION_REVISION = 199
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "ct"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "CT_").replace("CS_", "CT_")}


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

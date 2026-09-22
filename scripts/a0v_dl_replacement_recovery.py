#!/usr/bin/env python3
"""Create DL directly from the exact detached DK authority."""
from __future__ import annotations

import argparse
import json

import a0v_dk_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-dl"
replacement.AV_DIR = replacement.STATE / "dl"
replacement.AU_ID = "b651f4d7-b2a3-4032-a0d2-9b43743deb07"
replacement.AU_GENERATION = "fb16d08b-8fcb-4eb0-8c13-7698d16b83b4"
replacement.LOCK = "sha256:d696720fe77538523f00f0e3dd8685b38ecbed06f53c4a70e5c7a8c7b2f7eff2"
#AU_DISABLE/DETACH filled after DK retirement GREEN
replacement.AU_DISABLE_OPERATION = "796862c4-452d-4e2e-bab2-6300a139be33"
replacement.AU_DETACH_RECEIPT = "c2cdc20d-7efd-4896-87f6-8afe7c7878ca"
replacement.AU_DETACH_HASH = "sha256:0e686f8422c64c3ea7bb19813854a9f653dc6e601bbd363afd468257e5e1045e"
replacement.PREFIX = "a0v-qyh-clean-dl-20260922"
replacement.PREDECESSOR_ROUTE_REVISION = 314
replacement.PREDECESSOR_GROUP_REVISION = 341
replacement.DEFINITION_REVISION = 253
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "dl"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "DL_").replace("DK_", "DL_")}


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

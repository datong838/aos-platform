#!/usr/bin/env python3
"""Create CR directly from the exact detached CQ authority."""
from __future__ import annotations

import argparse
import json

import a0v_cq_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-cr"
replacement.AV_DIR = replacement.STATE / "cr"
replacement.AU_ID = "fff0b0d3-bf8f-44b0-b1b7-6a2972daeb80"
replacement.AU_GENERATION = "ae8a1005-99fb-48c5-9dfe-8f76590bc0c8"
replacement.LOCK = "sha256:6b3debbfebb5b16297f35e2271944a8a9775b2c178922d31525655088f919b50"
replacement.AU_DISABLE_OPERATION = "36c3d6ca-db24-4553-a0ec-8748006b3dd8"
replacement.AU_DETACH_RECEIPT = "2d8a382b-90f1-46c3-9100-c2310a949914"
replacement.AU_DETACH_HASH = "sha256:3b618e589557064bf049dd344fa9bdc345236d22a38ec2c1558d2a968d08b432"
replacement.PREFIX = "a0v-qyh-clean-cr-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 254
replacement.PREDECESSOR_GROUP_REVISION = 281
replacement.DEFINITION_REVISION = 193
replacement.PREDECESSOR_BINDING_REVISION = 11
replacement.PREDECESSOR_EXECUTION_EPOCH = 6
replacement.INSTALLATION_LABEL = "cr"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "CR_")}


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

#!/usr/bin/env python3
"""Create BQ directly from the exact detached BP authority."""
from __future__ import annotations

import argparse
import json

import a0v_bp_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-bq"
replacement.AV_DIR = replacement.STATE / "bq"
replacement.AU_ID = "17ba9792-9f24-42e4-9557-4d84547c7d97"
replacement.AU_GENERATION = "4f1bddfa-74a0-4fcb-b25e-f363139eed83"
replacement.LOCK = "sha256:d77d4dd49d57e0106483b4f4f90e7101dcc1ac70d1b6843ead31a4174ee74a2c"
replacement.AU_DISABLE_OPERATION = "90021097-2b72-4ecc-94dc-54dd571e1bfd"
replacement.AU_DETACH_RECEIPT = "ae6695f9-42bf-41a3-a09d-0f3c092e4793"
replacement.AU_DETACH_HASH = "sha256:f71f9eb5fdb860bd7cc068109686699c2db641a702d813fb9ec7b204f599b7c0"
replacement.PREFIX = "a0v-qyh-clean-bq-20260920"
replacement.PREDECESSOR_ROUTE_REVISION = 173
replacement.PREDECESSOR_GROUP_REVISION = 200
replacement.DEFINITION_REVISION = 124
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "bq"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "BQ_")}


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

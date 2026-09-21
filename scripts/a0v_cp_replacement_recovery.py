#!/usr/bin/env python3
"""Create CP directly from the exact detached CO authority."""
from __future__ import annotations

import argparse
import json

import a0v_co_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-cp"
replacement.AV_DIR = replacement.STATE / "cp"
replacement.AU_ID = "648b267b-bb8f-4582-ab29-288279f534c7"
replacement.AU_GENERATION = "db428c1b-2fe4-4869-8a69-ddffaa909ba7"
replacement.LOCK = "sha256:c0181c85dff7f0989c5f64652814065b6f273b2f31e349044dc125bd7bc486e9"
replacement.AU_DISABLE_OPERATION = "25fa94bf-b376-4c44-9ce9-147dc89c96d3"
replacement.AU_DETACH_RECEIPT = "d392b12f-9523-487e-aa9c-f473450e95cf"
replacement.AU_DETACH_HASH = "sha256:cccb32032a1403cfd5e5da25875f026330e2f95f743c6d78ba669f9ab576db96"
replacement.PREFIX = "a0v-qyh-clean-cp-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 248
replacement.PREDECESSOR_GROUP_REVISION = 275
replacement.DEFINITION_REVISION = 190
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "cp"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "CP_")}


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

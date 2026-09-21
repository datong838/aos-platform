#!/usr/bin/env python3
"""Create CV directly from the exact detached CU authority."""
from __future__ import annotations

import argparse
import json

import a0v_cu_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-cv"
replacement.AV_DIR = replacement.STATE / "cv"
replacement.AU_ID = "2c2d5506-1f80-4557-bf4b-00ead0258002"
replacement.AU_GENERATION = "bcaa7ea0-62b1-4238-8615-28db45e3014e"
replacement.LOCK = "sha256:3a1338060d903fc721f71e49b077ac130aa226f64a94e48d09d2ddab16f09200"
replacement.AU_DISABLE_OPERATION = "2acec273-b5c9-4fc6-8e55-943640f706f4"
replacement.AU_DETACH_RECEIPT = "ee918fb3-05db-4ed0-a678-0554225bb427"
replacement.AU_DETACH_HASH = "sha256:bdb72a10abfd3412182543a079b8c4bc813d0c7641186f6558aaa66560eff36e"
replacement.PREFIX = "a0v-qyh-clean-cv-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 266
replacement.PREDECESSOR_GROUP_REVISION = 293
replacement.DEFINITION_REVISION = 205
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "cv"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "CV_").replace("CU_", "CV_")}


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

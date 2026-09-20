#!/usr/bin/env python3
"""Create BJ directly from the exact detached BI authority."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_av_replacement_recovery as replacement


ROOT = Path(__file__).resolve().parents[1]
replacement.STATE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/replacement-bj"
replacement.AV_DIR = replacement.STATE / "bj"
replacement.AU_ID = "8ca245a1-8420-4590-b9e4-f92256fc22ce"
replacement.AU_GENERATION = "6f527122-a4a5-4056-a4e6-ca888f4b64d7"
replacement.LOCK = "sha256:969bb16d93cf922278bb2424c529cda2221eec1235d583b29ddc7f32991c9745"
replacement.AU_DISABLE_OPERATION = "96f687af-97ea-44cc-97e6-0c1cd292a8cf"
replacement.AU_DETACH_RECEIPT = "64375b18-389a-4e5b-bd17-c7e03a63edd6"
replacement.AU_DETACH_HASH = "sha256:0962da63b333d3bf94ea9cd9272e2aeba8afad44e3c678c560b4bd4872b56ddd"
replacement.PREFIX = "a0v-qyh-clean-bj-20260920"
replacement.PREDECESSOR_ROUTE_REVISION = 155
replacement.PREDECESSOR_GROUP_REVISION = 182
replacement.DEFINITION_REVISION = 109
replacement.PREDECESSOR_BINDING_REVISION = 8
replacement.PREDECESSOR_EXECUTION_EPOCH = 4
replacement.INSTALLATION_LABEL = "bj"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "BJ_")}


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

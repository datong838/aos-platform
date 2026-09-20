#!/usr/bin/env python3
"""Create BH directly from the exact detached BG authority."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_av_replacement_recovery as replacement


ROOT = Path(__file__).resolve().parents[1]
replacement.STATE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/replacement-bh"
replacement.AV_DIR = replacement.STATE / "bh"
replacement.AU_ID = "c52ab6db-176e-4378-ac88-2ee1bfc58487"
replacement.AU_GENERATION = "477c3f92-06f0-4dae-9445-ce6d09c3f462"
replacement.LOCK = "sha256:0e1880beeac4b28399b828c79b387c32e0be1cc41e982f786a8ddd8d04f88eb3"
replacement.AU_DISABLE_OPERATION = "95fbec3c-2248-4d43-928c-17b52d3742da"
replacement.AU_DETACH_RECEIPT = "48e4d856-6652-4903-af9f-49bf4774bc0d"
replacement.AU_DETACH_HASH = "sha256:6302314b46ee2699d9a05ef8552df2932fccb385f29a3442eba64c26458ad1b2"
replacement.PREFIX = "a0v-qyh-clean-bh-20260920"
replacement.PREDECESSOR_ROUTE_REVISION = 149
replacement.PREDECESSOR_GROUP_REVISION = 176
replacement.DEFINITION_REVISION = 103
replacement.PREDECESSOR_BINDING_REVISION = 8
replacement.PREDECESSOR_EXECUTION_EPOCH = 4
replacement.INSTALLATION_LABEL = "bh"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "BH_")}


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

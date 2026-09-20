#!/usr/bin/env python3
"""Create BL directly from the exact detached BK authority."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_av_replacement_recovery as replacement


ROOT = Path(__file__).resolve().parents[1]
replacement.STATE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/replacement-bl"
replacement.AV_DIR = replacement.STATE / "bl"
replacement.AU_ID = "8c78f903-ebd8-4589-97a0-afad76e209e0"
replacement.AU_GENERATION = "9ea4ba9d-1ef8-45a6-9060-1e4f37c87038"
replacement.LOCK = "sha256:462bc93fcd577556199e60c70eb21b3e5ae539b310f101aeb6095b9613babf71"
replacement.AU_DISABLE_OPERATION = "6db4b69b-0dbf-4a77-ac71-23cef91c6f50"
replacement.AU_DETACH_RECEIPT = "dfce56ec-4bff-4793-a5d5-dab4ad45aa1c"
replacement.AU_DETACH_HASH = "sha256:3fc2b8a9c3614912b1ac7a9c0d127677f3cc0187ed5c24209da10a963c71dca4"
replacement.PREFIX = "a0v-qyh-clean-bl-20260920"
replacement.PREDECESSOR_ROUTE_REVISION = 161
replacement.PREDECESSOR_GROUP_REVISION = 188
replacement.DEFINITION_REVISION = 115
replacement.PREDECESSOR_BINDING_REVISION = 8
replacement.PREDECESSOR_EXECUTION_EPOCH = 4
replacement.INSTALLATION_LABEL = "bl"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "BL_")}


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

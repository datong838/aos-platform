#!/usr/bin/env python3
"""Create AX as the formal direct replacement of detached AW."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_av_replacement_recovery as replacement


ROOT = Path(__file__).resolve().parents[1]
replacement.STATE = ROOT.parent / ".aos-recovery-20260919/state/q-advisor-baseline/replacement-ax"
replacement.AV_DIR = replacement.STATE / "ax"
replacement.AU_ID = "f94b9425-9bc4-4369-8ae3-138c50c9ab81"
replacement.AU_GENERATION = "a92f7bb2-3d90-4d88-9632-5fc9a70bd650"
replacement.LOCK = "sha256:f5e2bc370faaaecfc61498af1eac856ba6e4f17c77e6df84aded0bc0ade8ccd3"
replacement.AU_DISABLE_OPERATION = "0b77ae08-9c8c-4453-9f2b-709bddaca312"
replacement.AU_DETACH_RECEIPT = "0c50775b-62fe-4251-81f4-3c9a8709a90e"
replacement.AU_DETACH_HASH = "sha256:22b3fbf13e9fb92d3f7a4744a5f2787c9b0d3adf216727ed01439f1cb18d9226"
replacement.PREFIX = "a0v-qyh-clean-ax-20260919"
replacement.PREDECESSOR_ROUTE_REVISION = 122
replacement.PREDECESSOR_GROUP_REVISION = 149
replacement.DEFINITION_REVISION = 76
replacement.PREDECESSOR_BINDING_REVISION = 11
replacement.PREDECESSOR_EXECUTION_EPOCH = 6
replacement.INSTALLATION_LABEL = "ax"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "AX_")}


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

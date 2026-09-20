#!/usr/bin/env python3
"""Create BG directly from the exact detached BF authority."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_av_replacement_recovery as replacement


ROOT = Path(__file__).resolve().parents[1]
replacement.STATE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/replacement-bg"
replacement.AV_DIR = replacement.STATE / "bg"
replacement.AU_ID = "98a16beb-6342-48bd-9e12-989f3612ca00"
replacement.AU_GENERATION = "e33e0a9e-7296-4374-9aa9-113f1ed79b5f"
replacement.LOCK = "sha256:6cb2cef564ead4ace9dbeb091512b4f6cf0d8a8508782308a8cacea89bc921ed"
replacement.AU_DISABLE_OPERATION = "da0a2b14-f0f7-4f21-8513-c56bf4fbeb29"
replacement.AU_DETACH_RECEIPT = "03852ebe-20e0-4a41-a5fc-c9eb3aa927dd"
replacement.AU_DETACH_HASH = "sha256:ff354c79889453d270baa1b722abdb8785493f7f9432aa42fbe5b6ac7a61c925"
replacement.PREFIX = "a0v-qyh-clean-bg-20260920"
replacement.PREDECESSOR_ROUTE_REVISION = 146
replacement.PREDECESSOR_GROUP_REVISION = 173
replacement.DEFINITION_REVISION = 100
replacement.PREDECESSOR_BINDING_REVISION = 8
replacement.PREDECESSOR_EXECUTION_EPOCH = 4
replacement.INSTALLATION_LABEL = "bg"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "BG_")}


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

#!/usr/bin/env python3
"""Create AW as the formal direct replacement of detached AV."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_av_replacement_recovery as replacement


ROOT = Path(__file__).resolve().parents[1]
replacement.STATE = ROOT.parent / ".aos-recovery-20260919/state/q-advisor-baseline/replacement-aw"
replacement.AV_DIR = replacement.STATE / "aw"
replacement.AU_ID = "5f01eda8-ca5f-4892-8510-385704ccddb2"
replacement.AU_GENERATION = "17104053-f4c9-47e1-89b0-f3f353076dda"
replacement.LOCK = "sha256:9c4d67c428cb5f3e7bcb0e05dc553e87efa0c764683b7ab5ca4d5011336c5e47"
replacement.AU_DISABLE_OPERATION = "badb43f6-cb04-48ae-88ac-07f09122e872"
replacement.AU_DETACH_RECEIPT = "eed47855-2a96-4709-be2b-8283422a180a"
replacement.AU_DETACH_HASH = "sha256:9b60c491ad0476127c95740ab7f32276de6bb1ebeaf063326e70fe5a28f757ca"
replacement.PREFIX = "a0v-qyh-clean-aw-20260919"
replacement.PREDECESSOR_ROUTE_REVISION = 119
replacement.PREDECESSOR_GROUP_REVISION = 146
replacement.DEFINITION_REVISION = 76
replacement.PREDECESSOR_BINDING_REVISION = 8
replacement.PREDECESSOR_EXECUTION_EPOCH = 4
replacement.INSTALLATION_LABEL = "aw"


def run(action: str) -> dict:
    value = replacement.run(action)
    outcome = value.get("outcome", "").replace("AV_", "AW_")
    return {**value, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=replacement.ACTIONS)
    args = parser.parse_args()
    output = replacement.STATE / f"{args.action}-result.json"
    if output.exists():
        raise ValueError(f"immutable {args.action} output exists")
    value = run(args.action)
    replacement.freeze(output, value)
    print(json.dumps(value, ensure_ascii=False, default=str, indent=2))

#!/usr/bin/env python3
"""Create AY as the formal direct replacement of detached AX."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_av_replacement_recovery as replacement


ROOT = Path(__file__).resolve().parents[1]
replacement.STATE = ROOT.parent / ".aos-recovery-20260919/state/q-advisor-baseline/replacement-ay"
replacement.AV_DIR = replacement.STATE / "ay"
replacement.AU_ID = "be884663-0dba-4d9b-aa56-84caaf01147d"
replacement.AU_GENERATION = "a14c911b-6796-4d22-a3b0-1817cf502de9"
replacement.LOCK = "sha256:ae0c890abf2629daa136a615d9eadc4796e544f2e728ab4f567f0e7ebf65adc5"
replacement.AU_DISABLE_OPERATION = "8589a12c-aec2-4035-8937-f358dd1a8488"
replacement.AU_DETACH_RECEIPT = "622c8e25-ec0f-40dd-bf1f-ea57d180a800"
replacement.AU_DETACH_HASH = "sha256:583954da94992d30f7c5f9133c235eb3b17e0d8d190c27d61fe47621d41a6870"
replacement.PREFIX = "a0v-qyh-clean-ay-20260919"
replacement.PREDECESSOR_ROUTE_REVISION = 125
replacement.PREDECESSOR_GROUP_REVISION = 152
replacement.DEFINITION_REVISION = 79
replacement.PREDECESSOR_BINDING_REVISION = 8
replacement.PREDECESSOR_EXECUTION_EPOCH = 4
replacement.INSTALLATION_LABEL = "ay"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "AY_")}


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

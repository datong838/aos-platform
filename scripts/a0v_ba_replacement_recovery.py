#!/usr/bin/env python3
"""Create BA directly from the exact detached AZ authority."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_av_replacement_recovery as replacement


ROOT = Path(__file__).resolve().parents[1]
replacement.STATE = ROOT.parent / ".aos-recovery-20260919/state/q-advisor-baseline/replacement-ba"
replacement.AV_DIR = replacement.STATE / "ba"
replacement.AU_ID = "40eee6d9-fb03-4657-a83e-aeb38ec4aeeb"
replacement.AU_GENERATION = "7b6befaa-2f92-4e62-85f9-0ca060ec4b90"
replacement.LOCK = "sha256:7826b7400df634c9ad5f538b7db24026fc8930ee4bf6627b5d13277b2fa6afc5"
replacement.AU_DISABLE_OPERATION = "06849afe-ee19-486d-9d56-5247e947d8ab"
replacement.AU_DETACH_RECEIPT = "ee221609-d3d5-4227-8382-063d2ca0eab2"
replacement.AU_DETACH_HASH = "sha256:36b32dccacc9b7f8e78579fac44db423fe3ab470bc5165e205bf268c4cab8a7c"
replacement.PREFIX = "a0v-qyh-clean-ba-20260919"
replacement.PREDECESSOR_ROUTE_REVISION = 128
replacement.PREDECESSOR_GROUP_REVISION = 155
replacement.DEFINITION_REVISION = 82
replacement.PREDECESSOR_BINDING_REVISION = 8
replacement.PREDECESSOR_EXECUTION_EPOCH = 4
replacement.INSTALLATION_LABEL = "ba"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "BA_")}


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

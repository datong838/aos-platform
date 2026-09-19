#!/usr/bin/env python3
"""Create BD directly from the exact detached BC authority."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_av_replacement_recovery as replacement


ROOT = Path(__file__).resolve().parents[1]
replacement.STATE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/replacement-bd"
replacement.AV_DIR = replacement.STATE / "bd"
replacement.AU_ID = "3b895c30-34ca-4710-b978-02645d49c83a"
replacement.AU_GENERATION = "31776dcd-e28f-4b6d-ae45-75fb0ab5a505"
replacement.LOCK = "sha256:c59c7f036bb2a5e2892e854a79d1baca5b6ca915a191e7376812de9de54106a6"
replacement.AU_DISABLE_OPERATION = "b713c722-902f-4486-b3bb-4eca02a621b7"
replacement.AU_DETACH_RECEIPT = "39bb3f98-78b6-444b-9d5c-a51991b03f42"
replacement.AU_DETACH_HASH = "sha256:7351a8aca2751c721b96ef1c72352318a507a18598930e13fbc79667f3bc169c"
replacement.PREFIX = "a0v-qyh-clean-bd-20260920"
replacement.PREDECESSOR_ROUTE_REVISION = 137
replacement.PREDECESSOR_GROUP_REVISION = 164
replacement.DEFINITION_REVISION = 91
replacement.PREDECESSOR_BINDING_REVISION = 8
replacement.PREDECESSOR_EXECUTION_EPOCH = 4
replacement.INSTALLATION_LABEL = "bd"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "BD_")}


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

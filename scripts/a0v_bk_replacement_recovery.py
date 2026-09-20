#!/usr/bin/env python3
"""Create BK directly from the exact detached BJ authority."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_av_replacement_recovery as replacement


ROOT = Path(__file__).resolve().parents[1]
replacement.STATE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/replacement-bk"
replacement.AV_DIR = replacement.STATE / "bk"
replacement.AU_ID = "2c3972b1-67c1-400d-aa63-b90de369f5de"
replacement.AU_GENERATION = "8dafd4ae-d42b-4f2f-accb-b5a49e7c9a3b"
replacement.LOCK = "sha256:d01e0d465ac65672a7edac4be6b453d16958037d15fff75220b6d5dee4458128"
replacement.AU_DISABLE_OPERATION = "2300de61-0b54-413a-97e7-4e37e3b20768"
replacement.AU_DETACH_RECEIPT = "2c5d28d5-cfcc-474d-827d-d0031d0de4d8"
replacement.AU_DETACH_HASH = "sha256:9fff94f0bc18f763292002f838bb0f197e9548e59eefe92d2722cd71d307281d"
replacement.PREFIX = "a0v-qyh-clean-bk-20260920"
replacement.PREDECESSOR_ROUTE_REVISION = 158
replacement.PREDECESSOR_GROUP_REVISION = 185
replacement.DEFINITION_REVISION = 112
replacement.PREDECESSOR_BINDING_REVISION = 8
replacement.PREDECESSOR_EXECUTION_EPOCH = 4
replacement.INSTALLATION_LABEL = "bk"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "BK_")}


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

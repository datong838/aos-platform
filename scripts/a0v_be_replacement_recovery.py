#!/usr/bin/env python3
"""Create BE directly from the exact detached BD authority."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_av_replacement_recovery as replacement


ROOT = Path(__file__).resolve().parents[1]
replacement.STATE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/replacement-be"
replacement.AV_DIR = replacement.STATE / "be"
replacement.AU_ID = "c2d6ef97-30ec-4980-9421-54a899607853"
replacement.AU_GENERATION = "f5e01f1d-e6c5-425a-9145-6f7a82ec65e5"
replacement.LOCK = "sha256:0acab1c9950e014737c8e5814750bca0118bf265e9dfeb382a52d32b45a71547"
replacement.AU_DISABLE_OPERATION = "f5f52787-c6f1-468b-9e7e-878113942c65"
replacement.AU_DETACH_RECEIPT = "c896fec3-dbe2-46fe-be60-3cc249b4b4ed"
replacement.AU_DETACH_HASH = "sha256:8845a269e68dd54bfa89ca1e8a1f5785e199fb80985f86d08f93b5b570581495"
replacement.PREFIX = "a0v-qyh-clean-be-20260920"
replacement.PREDECESSOR_ROUTE_REVISION = 140
replacement.PREDECESSOR_GROUP_REVISION = 167
replacement.DEFINITION_REVISION = 94
replacement.PREDECESSOR_BINDING_REVISION = 8
replacement.PREDECESSOR_EXECUTION_EPOCH = 4
replacement.INSTALLATION_LABEL = "be"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "BE_")}


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

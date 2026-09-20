#!/usr/bin/env python3
"""Create BI directly from the exact detached BH authority."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_av_replacement_recovery as replacement


ROOT = Path(__file__).resolve().parents[1]
replacement.STATE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/replacement-bi"
replacement.AV_DIR = replacement.STATE / "bi"
replacement.AU_ID = "7b7d4319-e639-48c9-971b-0efbfb9251ef"
replacement.AU_GENERATION = "f6023b7c-ca6f-49ac-b9ff-4dcbca62745c"
replacement.LOCK = "sha256:c920a20eec94c3f9da2030da31a05f5b8f314f8e9264c5d5d8b4bcc02e4c28fa"
replacement.AU_DISABLE_OPERATION = "33167268-e7e6-42fc-90f9-e2cb83e6f932"
replacement.AU_DETACH_RECEIPT = "8609e798-2f61-43df-9838-cad7da02c230"
replacement.AU_DETACH_HASH = "sha256:25b34bd970571e9d9f402380fa483433f6343a441f969e6f6b5c044e60975ea9"
replacement.PREFIX = "a0v-qyh-clean-bi-20260920"
replacement.PREDECESSOR_ROUTE_REVISION = 152
replacement.PREDECESSOR_GROUP_REVISION = 179
replacement.DEFINITION_REVISION = 106
replacement.PREDECESSOR_BINDING_REVISION = 8
replacement.PREDECESSOR_EXECUTION_EPOCH = 4
replacement.INSTALLATION_LABEL = "bi"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "BI_")}


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

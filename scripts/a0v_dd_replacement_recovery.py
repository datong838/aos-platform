#!/usr/bin/env python3
"""Create DD directly from the exact detached DC authority."""
from __future__ import annotations

import argparse
import json

import a0v_dc_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-dd"
replacement.AV_DIR = replacement.STATE / "dd"
replacement.AU_ID = "02d39eb8-174e-432f-9776-57de7c4436c8"
replacement.AU_GENERATION = "bd59503f-eb9e-4fe6-a09d-a92a3b924682"
replacement.LOCK = "sha256:4c19a327b9536269eb3582b82814f3342237d8c95bb5c65c29e402d55f86aa4b"
replacement.AU_DISABLE_OPERATION = "2a9ad4a5-0da7-488a-a474-bcee64eaa08e"
replacement.AU_DETACH_RECEIPT = "c1e5de00-55dc-4eb0-bb57-21524e784c53"
replacement.AU_DETACH_HASH = "sha256:35973282a15a5ee626e3ef2429b0a5935ec5ca37a0ec3e496bced3d6f91d4e4d"
replacement.PREFIX = "a0v-qyh-clean-dd-20260922"
replacement.PREDECESSOR_ROUTE_REVISION = 290
replacement.PREDECESSOR_GROUP_REVISION = 317
replacement.DEFINITION_REVISION = 229
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "dd"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "DD_").replace("DC_", "DD_")}


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

#!/usr/bin/env python3
"""Create CO directly from the exact detached CN authority."""
from __future__ import annotations

import argparse
import json

import a0v_cn_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-co"
replacement.AV_DIR = replacement.STATE / "co"
replacement.AU_ID = "1366f4dd-47d9-42c1-b26a-759c7bd556da"
replacement.AU_GENERATION = "cd0601e0-2668-496d-9f93-561d2e69a170"
replacement.LOCK = "sha256:18045e8ebd31484b42a6ae4cebb9eb81b5d56be02b3a5929405ad2957f0c96bb"
replacement.AU_DISABLE_OPERATION = "993d8b13-fcf5-4a14-9410-b601d6f7a891"
replacement.AU_DETACH_RECEIPT = "5f72b40e-543f-49e6-947c-a636a41cee99"
replacement.AU_DETACH_HASH = "sha256:46f951422c2f99c4cc63103b202ae83c8b04bff574282204f5f89f90d3fff09c"
replacement.PREFIX = "a0v-qyh-clean-co-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 245
replacement.PREDECESSOR_GROUP_REVISION = 272
replacement.DEFINITION_REVISION = 187
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "co"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "CO_")}


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

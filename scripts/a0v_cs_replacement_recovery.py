#!/usr/bin/env python3
"""Create CS directly from the exact detached CR authority."""
from __future__ import annotations

import argparse
import json

import a0v_cr_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-cs"
replacement.AV_DIR = replacement.STATE / "cs"
replacement.AU_ID = "913cb7a1-4912-471a-abbf-452e3ce999a9"
replacement.AU_GENERATION = "a4a16448-5581-4948-b962-777ff601e855"
replacement.LOCK = "sha256:c3513e45b002c90a810034eab554ed58c6aba4123be24349bbba0f7d24777334"
replacement.AU_DISABLE_OPERATION = "0667be2f-3ebd-484b-99f0-dfb135a6f9c2"
replacement.AU_DETACH_RECEIPT = "14c1b753-d557-4441-bf7f-89ad5ab48be5"
replacement.AU_DETACH_HASH = "sha256:bd7ff2a43c944fe8aed88f89e9af82b511a36a8e029d86bb2428369ba3f9cc06"
replacement.PREFIX = "a0v-qyh-clean-cs-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 257
replacement.PREDECESSOR_GROUP_REVISION = 284
replacement.DEFINITION_REVISION = 196
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "cs"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "CS_")}


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

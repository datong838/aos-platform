#!/usr/bin/env python3
"""Create CB directly from the exact detached CA authority."""
from __future__ import annotations

import argparse
import json

import a0v_ca_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-cb"
replacement.AV_DIR = replacement.STATE / "cb"
replacement.AU_ID = "0d834ab1-fd2b-4dbc-b9a5-0f0dee712647"
replacement.AU_GENERATION = "1f18a077-12c6-4242-982a-0c3fa1159540"
replacement.LOCK = "sha256:00c2ccaa82e00eb0e23f4e7dcd2491b674cb37caaf5d0e1a027709f6c8f47d7a"
replacement.AU_DISABLE_OPERATION = "077c473a-dd7c-463b-87d3-eafb228cfbc5"
replacement.AU_DETACH_RECEIPT = "bfffc7e7-5606-4101-9b5e-bc729ddb26ef"
replacement.AU_DETACH_HASH = "sha256:f4178b7c27dc9addc0fe17a13f446302af66d291960cd1c7a8aae6aab98554ce"
replacement.PREFIX = "a0v-qyh-clean-cb-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 206
replacement.PREDECESSOR_GROUP_REVISION = 233
replacement.DEFINITION_REVISION = 148
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "cb"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "CB_")}


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

#!/usr/bin/env python3
"""Create CM directly from the exact detached CL authority."""
from __future__ import annotations

import argparse
import json

import a0v_cl_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-cm"
replacement.AV_DIR = replacement.STATE / "cm"
replacement.AU_ID = "64e49f66-b0ef-4676-91c1-eb05f6d1d0b1"
replacement.AU_GENERATION = "a583218d-f65b-4697-9e60-7281a0bff66e"
replacement.LOCK = "sha256:9e4ab375110d6d458b98012872bc35a39545afc7e6d547ed48c57667f4838a8e"
replacement.AU_DISABLE_OPERATION = "a4b94187-2a96-4779-af57-02e4b659a90d"
replacement.AU_DETACH_RECEIPT = "03e11531-9fb5-4453-80dd-2d2d07051bec"
replacement.AU_DETACH_HASH = "sha256:b93907af1a3ace36e10d83da4e199da17c80aaa0b9cdbc557b88a54fed721992"
replacement.PREFIX = "a0v-qyh-clean-cm-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 239
replacement.PREDECESSOR_GROUP_REVISION = 266
replacement.DEFINITION_REVISION = 181
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "cm"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "CM_")}


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

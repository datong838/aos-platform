#!/usr/bin/env python3
"""Create CJ directly from the exact detached CI authority."""
from __future__ import annotations

import argparse
import json

import a0v_ci_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-cj"
replacement.AV_DIR = replacement.STATE / "cj"
replacement.AU_ID = "1b9f500d-48a0-4f2c-8284-3db26e5cd4e7"
replacement.AU_GENERATION = "8de8994b-ad87-4039-a851-d944153bca08"
replacement.LOCK = "sha256:06757616841bff14cebd4175476baa08d8ebd1fd81a5ce06cd1b2abb968af759"
replacement.AU_DISABLE_OPERATION = "33240efc-8111-49ef-ac0c-759ae37868cc"
replacement.AU_DETACH_RECEIPT = "700c9914-c3ed-4360-8769-5f8d09307352"
replacement.AU_DETACH_HASH = "sha256:5cc5d6e9cf6a284f6e9533438f225291042162573aee209ff9b9cbc20893c4dd"
replacement.PREFIX = "a0v-qyh-clean-cj-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 230
replacement.PREDECESSOR_GROUP_REVISION = 257
replacement.DEFINITION_REVISION = 172
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "cj"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "CJ_")}


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

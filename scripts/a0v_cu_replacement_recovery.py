#!/usr/bin/env python3
"""Create CU directly from the exact detached CT authority."""
from __future__ import annotations

import argparse
import json

import a0v_ct_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-cu"
replacement.AV_DIR = replacement.STATE / "cu"
replacement.AU_ID = "b4847c85-b452-4c87-bf56-8a57bc9f8d25"
replacement.AU_GENERATION = "0d234db2-8b76-4ec8-a14a-a8c6eec9bbc6"
replacement.LOCK = "sha256:c450112c2c3d926d714dee8764c1c28b0f6940fca70555f0733902ad69e53988"
replacement.AU_DISABLE_OPERATION = "4704b467-5d69-4ee3-b4e5-e755c5e98eea"
replacement.AU_DETACH_RECEIPT = "b1101390-ca5d-43bf-bc6a-c3bc0fc1d4f1"
replacement.AU_DETACH_HASH = "sha256:8809a0a0ff8a8e69291d737a28277a48ef6faea6b8520ae658c55b320ace7123"
replacement.PREFIX = "a0v-qyh-clean-cu-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 263
replacement.PREDECESSOR_GROUP_REVISION = 290
replacement.DEFINITION_REVISION = 202
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "cu"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "CU_").replace("CT_", "CU_")}


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

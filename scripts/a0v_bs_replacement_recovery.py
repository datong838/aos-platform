#!/usr/bin/env python3
"""Create BS directly from the exact detached BR authority."""
from __future__ import annotations

import argparse
import json

import a0v_br_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-bs"
replacement.AV_DIR = replacement.STATE / "bs"
replacement.AU_ID = "fddfa0b0-158c-4271-b1ea-dc4e1e36e293"
replacement.AU_GENERATION = "981d7a2d-3bbe-4cc1-a8d9-c872be0147d3"
replacement.LOCK = "sha256:8fdef3f38ad4a6967cd378dea37ff7e540b31046e424de6bbc8e3a49ff9ce414"
replacement.AU_DISABLE_OPERATION = "91705b53-691b-4ebc-bab5-ba21945c9ec9"
replacement.AU_DETACH_RECEIPT = "f4ca1d45-b002-47d2-b56a-15f6b57f7b3b"
replacement.AU_DETACH_HASH = "sha256:2a476a8b1e9f22247726c75ef5dae82eb043b339a501e7ea13b776324c6b48bc"
replacement.PREFIX = "a0v-qyh-clean-bs-20260920"
replacement.PREDECESSOR_ROUTE_REVISION = 179
replacement.PREDECESSOR_GROUP_REVISION = 206
replacement.DEFINITION_REVISION = 127
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "bs"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "BS_")}


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

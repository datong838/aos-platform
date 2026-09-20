#!/usr/bin/env python3
"""Create BR directly from the exact detached BQ authority."""
from __future__ import annotations

import argparse
import json

import a0v_bq_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-br"
replacement.AV_DIR = replacement.STATE / "br"
replacement.AU_ID = "4faaf3b7-2d10-4961-99db-5bf52b7b8a63"
replacement.AU_GENERATION = "b53ce5ac-169c-4d69-9780-58beb8ad736c"
replacement.LOCK = "sha256:b072f76743abd5ae543c7cf37ad0bfb3e569a40b188998a03d2e94a5e7ae713f"
replacement.AU_DISABLE_OPERATION = "126a0ab8-6fa0-464b-b97c-dfe47862db0a"
replacement.AU_DETACH_RECEIPT = "82c3e7a5-64ad-4d4d-9cd1-d7c2c2f8fa3b"
replacement.AU_DETACH_HASH = "sha256:ae12194af3b1991fe3ba7e148d67d90a47d7213d33cb707ad7956380bdf98e4f"
replacement.PREFIX = "a0v-qyh-clean-br-20260920"
replacement.PREDECESSOR_ROUTE_REVISION = 176
replacement.PREDECESSOR_GROUP_REVISION = 203
replacement.DEFINITION_REVISION = 124
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "br"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "BR_")}


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

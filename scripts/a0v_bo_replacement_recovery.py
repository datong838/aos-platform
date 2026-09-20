#!/usr/bin/env python3
"""Create BO directly from the exact detached BN authority."""
from __future__ import annotations

import argparse
import json

import a0v_bn_replacement_recovery as canonical


replacement = canonical.replacement
replacement.STATE = canonical.BASE / "replacement-bo"
replacement.AV_DIR = replacement.STATE / "bo"
replacement.AU_ID = "d89bca67-4472-4b43-b0bd-ae8a2e0459f5"
replacement.AU_GENERATION = "a43b3e64-7bb4-454c-822e-58bc13acbcaa"
replacement.LOCK = "sha256:d0f24b0d57a20c0c2606609794c386471484711d823f63c05752db160ea09d9b"
replacement.AU_DISABLE_OPERATION = "ff01e6a5-436a-46b1-a757-8e78b3344748"
replacement.AU_DETACH_RECEIPT = "f581970a-fcff-403b-ad64-57c26e38831e"
replacement.AU_DETACH_HASH = "sha256:ec476774123dea036e212e6164b471510a4a536c3cf2ff137149d0437dc038d4"
replacement.PREFIX = "a0v-qyh-clean-bo-20260920"
replacement.PREDECESSOR_ROUTE_REVISION = 167
replacement.PREDECESSOR_GROUP_REVISION = 194
replacement.DEFINITION_REVISION = 118
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "bo"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "BO_")}


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

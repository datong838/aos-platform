#!/usr/bin/env python3
"""Create DH directly from the exact detached DG authority."""
from __future__ import annotations

import argparse
import json

import a0v_dg_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-dh"
replacement.AV_DIR = replacement.STATE / "dh"
replacement.AU_ID = "d551d104-f240-4b27-b738-1ef47129b5a4"
replacement.AU_GENERATION = "6c1780ab-746b-4303-a9ad-dc30039af8a4"
replacement.LOCK = "sha256:63f93357f433f7b9c85c0316eb746ea66b61642b00cde388fabde339a33312a2"
replacement.AU_DISABLE_OPERATION = "1a745c65-7ad2-41ff-ae0a-55427d8462dc"
replacement.AU_DETACH_RECEIPT = "6d21f82c-7521-4c36-89c0-06f360339b02"
replacement.AU_DETACH_HASH = "sha256:7bd17d373e1281fbb5768e5b99b839b617d30c89a2e3e088afcb285818129c22"
replacement.PREFIX = "a0v-qyh-clean-dh-20260922"
replacement.PREDECESSOR_ROUTE_REVISION = 302
replacement.PREDECESSOR_GROUP_REVISION = 329
replacement.DEFINITION_REVISION = 241
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "dh"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "DH_").replace("DG_", "DH_")}


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

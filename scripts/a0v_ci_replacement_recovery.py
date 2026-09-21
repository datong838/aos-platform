#!/usr/bin/env python3
"""Create CI directly from the exact detached CH authority."""
from __future__ import annotations

import argparse
import json

import a0v_ch_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-ci"
replacement.AV_DIR = replacement.STATE / "ci"
replacement.AU_ID = "990f96f7-764e-4002-b691-fc5eb8d4335c"
replacement.AU_GENERATION = "0521ccf8-304a-45b3-b820-dc6ebd64b51b"
replacement.LOCK = "sha256:0a550a6efdbd48ea06b35f7559d83b6840dfaae117b6bfd6fa9dbf46733c9ea6"
replacement.AU_DISABLE_OPERATION = "2c28623c-d418-4123-8846-89f4c4d905e9"
replacement.AU_DETACH_RECEIPT = "bef972d2-2c5f-4cd3-9448-b7e94ff7594d"
replacement.AU_DETACH_HASH = "sha256:c1537c4af534489422e2fbe819d7ed079db9c25c9d1702d214c77097af8ffdac"
replacement.PREFIX = "a0v-qyh-clean-ci-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 227
replacement.PREDECESSOR_GROUP_REVISION = 254
replacement.DEFINITION_REVISION = 169
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "ci"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "CI_")}


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

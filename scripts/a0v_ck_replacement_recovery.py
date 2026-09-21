#!/usr/bin/env python3
"""Create CK directly from the exact detached CJ authority."""
from __future__ import annotations

import argparse
import json

import a0v_cj_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-ck"
replacement.AV_DIR = replacement.STATE / "ck"
replacement.AU_ID = "184e0d1d-128a-462c-b677-d19bc5bf0891"
replacement.AU_GENERATION = "f45f46a9-56ae-49b5-966d-083cdf19282b"
replacement.LOCK = "sha256:f96d6d2a702e0b4847ae259233fc50976ca5763462eb975359b5344edf758537"
replacement.AU_DISABLE_OPERATION = "69469d23-01f1-41e1-8263-14dbbde43595"
replacement.AU_DETACH_RECEIPT = "54b8272c-dae1-4dca-833e-90a40bc77fba"
replacement.AU_DETACH_HASH = "sha256:9d8812adc4d156ee37149d5791920669c5684915f0399be6030cb358eb14e09d"
replacement.PREFIX = "a0v-qyh-clean-ck-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 233
replacement.PREDECESSOR_GROUP_REVISION = 260
replacement.DEFINITION_REVISION = 175
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "ck"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "CK_")}


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

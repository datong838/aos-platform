#!/usr/bin/env python3
"""Create DK directly from the exact detached DJ authority."""
from __future__ import annotations

import argparse
import json

import a0v_dj_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-dk"
replacement.AV_DIR = replacement.STATE / "dk"
replacement.AU_ID = "aca93a08-341f-4bd6-9e94-ed7fde3aed66"
replacement.AU_GENERATION = "6ce73106-f945-4d34-a818-552303fec308"
replacement.LOCK = "sha256:1010c16bb85c06d0dd36e9d33d7de2922b1ab0413e155b4feadf18744c356f89"
replacement.AU_DISABLE_OPERATION = "1e2eafae-df4f-4224-af78-aed094d76b53"
replacement.AU_DETACH_RECEIPT = "5f4ea80e-31f3-4357-b80b-def70eb6cb03"
replacement.AU_DETACH_HASH = "sha256:865b94d856a1d753227f88cd90c285cf3a21d63ab07dc4a8707f0fd0bbce08da"
replacement.PREFIX = "a0v-qyh-clean-dk-20260922"
replacement.PREDECESSOR_ROUTE_REVISION = 311
replacement.PREDECESSOR_GROUP_REVISION = 338
replacement.DEFINITION_REVISION = 250
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "dk"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "DK_").replace("DJ_", "DK_")}


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

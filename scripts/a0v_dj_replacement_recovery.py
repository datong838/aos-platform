#!/usr/bin/env python3
"""Create DJ directly from the exact detached DI authority."""
from __future__ import annotations

import argparse
import json

import a0v_di_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-dj"
replacement.AV_DIR = replacement.STATE / "dj"
replacement.AU_ID = "c8298a5d-9d94-4c37-81c9-508e2f0faf60"
replacement.AU_GENERATION = "56950fc1-4007-497a-8a09-df133a1950c1"
replacement.LOCK = "sha256:306ffd56004521bf793df38eb4887287afbec98279c169e64aaae469a5dbfffc"
replacement.AU_DISABLE_OPERATION = "b46ecb89-ce38-409b-8153-b502e7739f2b"
replacement.AU_DETACH_RECEIPT = "6ac1c229-2368-4201-a208-4aa96a846e06"
replacement.AU_DETACH_HASH = "sha256:e31dc9ae7b95b12cbbc5ad6294030598d8459cc55835c13652928d85c2e3511d"
replacement.PREFIX = "a0v-qyh-clean-dj-20260922"
replacement.PREDECESSOR_ROUTE_REVISION = 308
replacement.PREDECESSOR_GROUP_REVISION = 335
replacement.DEFINITION_REVISION = 247
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "dj"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "DJ_").replace("DI_", "DJ_")}


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

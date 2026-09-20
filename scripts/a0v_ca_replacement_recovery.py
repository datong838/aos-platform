#!/usr/bin/env python3
"""Create CA directly from the exact detached BZ authority."""
from __future__ import annotations

import argparse
import json

import a0v_bz_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-ca"
replacement.AV_DIR = replacement.STATE / "ca"
replacement.AU_ID = "9b30837c-da4d-4cfd-b438-de40aa5e3d7a"
replacement.AU_GENERATION = "6f1e6e77-24aa-4052-9102-88e4a432fe55"
replacement.LOCK = "sha256:710bd45e92ed91c1e9a634e12eb4bdd8d9a4c8cee32191537dcd62c929e277af"
replacement.AU_DISABLE_OPERATION = "447af99f-fbb2-4142-971d-e5458a90b468"
replacement.AU_DETACH_RECEIPT = "a5ab50b1-aa8a-4418-9ed9-59a454d9055d"
replacement.AU_DETACH_HASH = "sha256:3f234f4c5d965b0b824383ff20f980c2f4ed2555c0aab59aac037289b4bfd9eb"
replacement.PREFIX = "a0v-qyh-clean-ca-20260921"
replacement.PREDECESSOR_ROUTE_REVISION = 203
replacement.PREDECESSOR_GROUP_REVISION = 230
replacement.DEFINITION_REVISION = 145
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "ca"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "CA_")}


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

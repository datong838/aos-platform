#!/usr/bin/env python3
"""Create DF directly from the exact detached DE authority."""
from __future__ import annotations

import argparse
import json

import a0v_de_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-df"
replacement.AV_DIR = replacement.STATE / "df"
replacement.AU_ID = "5d993078-18ec-4302-9286-7081a1463cc0"
replacement.AU_GENERATION = "f5181ad4-e304-4533-aa4a-0f30b3c6dac3"
replacement.LOCK = "sha256:46f9998335c83c6e82131e6c767925fe3a8bbb48c06035a30f6ac19ba54b9b15"
replacement.AU_DISABLE_OPERATION = "ca18531e-9554-462c-ac76-c8e315d26a7b"
replacement.AU_DETACH_RECEIPT = "3cda5059-7651-42ec-8c2a-bf60e3e1dbc1"
replacement.AU_DETACH_HASH = "sha256:51d2e740fe62d7e614d73c1c3786b91d2f030d37882a7127f1db14070c884208"
replacement.PREFIX = "a0v-qyh-clean-df-20260922"
replacement.PREDECESSOR_ROUTE_REVISION = 296
replacement.PREDECESSOR_GROUP_REVISION = 323
replacement.DEFINITION_REVISION = 235
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "df"


def run(action: str) -> dict:
    value = replacement.run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "DF_").replace("DE_", "DF_")}


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

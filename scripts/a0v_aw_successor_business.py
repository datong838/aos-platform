#!/usr/bin/env python3
"""Register AW from AV's exact detach Receipt after replacement enable."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_aw_replacement_recovery as aw_replacement
import a0v_av_successor_business as successor


ROOT = Path(__file__).resolve().parents[1]
CREATE = json.loads((aw_replacement.replacement.STATE / "create-av-result.json").read_text(encoding="utf-8"))
STAGE = json.loads((aw_replacement.replacement.STATE / "stage-av-result.json").read_text(encoding="utf-8"))
successor.STATE = aw_replacement.replacement.STATE / "registration-aw"
successor.AV_ID = CREATE["installationId"]
successor.AV_GENERATION = STAGE["binding"]["generation"]
successor.LOCK = CREATE["lockHash"]
successor.CONFIG = STAGE["staged"]["configRef"]
successor.AU_ID = "5f01eda8-ca5f-4892-8510-385704ccddb2"
successor.AU_GENERATION = "17104053-f4c9-47e1-89b0-f3f353076dda"
successor.DETACH = "eed47855-2a96-4709-be2b-8283422a180a"
successor.DETACH_HASH = "sha256:9b60c491ad0476127c95740ab7f32276de6bb1ebeaf063326e70fe5a28f757ca"
successor.KEY = "a0v-qyh-clean-generation-aw-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 8
successor.PREDECESSOR_EXECUTION_EPOCH = 4
successor.PREDECESSOR_ROUTE_REVISION = 119
successor.PREDECESSOR_GROUP_REVISION = 146
successor.replacement_module = lambda: aw_replacement.replacement

AW_ID = successor.AV_ID
AW_GENERATION = successor.AV_GENERATION
# The shared AV cutover executor resolves these stable compatibility names.
AV_ID = AW_ID
AV_GENERATION = AW_GENERATION
LOCK = successor.LOCK
CONFIG = successor.CONFIG
GROUP = successor.GROUP
KEY = successor.KEY
ACTOR = successor.ACTOR
STATE = successor.STATE


def setup():
    return successor.setup()


def current_request():
    return successor.current_request()


def register(plane, request):
    result = successor.register(plane, request)
    return {**result, "outcome": "CURRENT_AW_SUCCESSOR_REGISTERED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preview", "register"])
    args = parser.parse_args()
    plane = setup()
    request = current_request()
    result = ({"outcome": "CURRENT_AW_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()} if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

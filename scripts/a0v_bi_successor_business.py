#!/usr/bin/env python3
"""Register BI directly from the exact detached BH authority."""
from __future__ import annotations

import argparse
import json

import a0v_av_successor_business as successor
import a0v_bi_replacement_recovery as bi_replacement


successor.STATE = bi_replacement.replacement.STATE / "registration-bi"
successor.AV_ID = "8ca245a1-8420-4590-b9e4-f92256fc22ce"
successor.AV_GENERATION = "6f527122-a4a5-4056-a4e6-ca888f4b64d7"
successor.LOCK = "sha256:969bb16d93cf922278bb2424c529cda2221eec1235d583b29ddc7f32991c9745"
successor.CONFIG = {"configurationId": "f9fbd566-eae4-400e-a89d-5ada9f1db49b", "revision": 1,
                    "hash": "sha256:0c242ce2bf7d9a7422ec7158e4d1de9019ec57fa8dbcfdcc743c6ff588b58683"}
successor.AU_ID = "7b7d4319-e639-48c9-971b-0efbfb9251ef"
successor.AU_GENERATION = "f6023b7c-ca6f-49ac-b9ff-4dcbca62745c"
successor.DETACH = "8609e798-2f61-43df-9838-cad7da02c230"
successor.DETACH_HASH = "sha256:25b34bd970571e9d9f402380fa483433f6343a441f969e6f6b5c044e60975ea9"
successor.KEY = "a0v-qyh-clean-generation-bi-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 8
successor.PREDECESSOR_EXECUTION_EPOCH = 4
successor.PREDECESSOR_ROUTE_REVISION = 152
successor.PREDECESSOR_GROUP_REVISION = 179
successor.replacement_module = lambda: bi_replacement.replacement

BI_ID = successor.AV_ID
BI_GENERATION = successor.AV_GENERATION
AV_ID = BI_ID
AV_GENERATION = BI_GENERATION
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
    return {**result, "outcome": "CURRENT_BI_SUCCESSOR_REGISTERED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preview", "register"])
    args = parser.parse_args()
    plane = setup()
    request = current_request()
    result = ({"outcome": "CURRENT_BI_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()} if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

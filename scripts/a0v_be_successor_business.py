#!/usr/bin/env python3
"""Register BE directly from the exact BD detach authority."""
from __future__ import annotations

import argparse
import json

import a0v_av_successor_business as successor
import a0v_be_replacement_recovery as be_replacement


successor.STATE = be_replacement.replacement.STATE / "registration-be"
successor.AV_ID = "1a0f801f-d8f3-43af-a31e-5c9fc8161d6d"
successor.AV_GENERATION = "93349d9b-ad61-4919-9cbd-e1e9b02545bb"
successor.LOCK = "sha256:30602cd6e4b4adebd8b1710abc6cd5204284ab62d12598fde4fa527a72b8e05d"
successor.CONFIG = {"configurationId": "0e737e1e-a8b3-449b-bc96-3ff603e6de0a", "revision": 1,
                    "hash": "sha256:8a6eaf3b111180b45d051b89319b236eca69b64835e9a61459aacba9ef59d2c2"}
successor.AU_ID = "c2d6ef97-30ec-4980-9421-54a899607853"
successor.AU_GENERATION = "f5e01f1d-e6c5-425a-9145-6f7a82ec65e5"
successor.DETACH = "c896fec3-dbe2-46fe-be60-3cc249b4b4ed"
successor.DETACH_HASH = "sha256:8845a269e68dd54bfa89ca1e8a1f5785e199fb80985f86d08f93b5b570581495"
successor.KEY = "a0v-qyh-clean-generation-be-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 8
successor.PREDECESSOR_EXECUTION_EPOCH = 4
successor.PREDECESSOR_ROUTE_REVISION = 140
successor.PREDECESSOR_GROUP_REVISION = 167
successor.replacement_module = lambda: be_replacement.replacement

BE_ID = successor.AV_ID
BE_GENERATION = successor.AV_GENERATION
AV_ID = BE_ID
AV_GENERATION = BE_GENERATION
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
    return {**result, "outcome": "CURRENT_BE_SUCCESSOR_REGISTERED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preview", "register"])
    args = parser.parse_args()
    plane = setup()
    request = current_request()
    result = ({"outcome": "CURRENT_BE_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()} if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

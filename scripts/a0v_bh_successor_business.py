#!/usr/bin/env python3
"""Register BH directly from the exact detached BG authority."""
from __future__ import annotations

import argparse
import json

import a0v_av_successor_business as successor
import a0v_bh_replacement_recovery as bh_replacement


successor.STATE = bh_replacement.replacement.STATE / "registration-bh"
successor.AV_ID = "7b7d4319-e639-48c9-971b-0efbfb9251ef"
successor.AV_GENERATION = "f6023b7c-ca6f-49ac-b9ff-4dcbca62745c"
successor.LOCK = "sha256:c920a20eec94c3f9da2030da31a05f5b8f314f8e9264c5d5d8b4bcc02e4c28fa"
successor.CONFIG = {"configurationId": "6b63f3e9-6805-48eb-a4cb-08e15d1e52a5", "revision": 1,
                    "hash": "sha256:42681ea6edad421e488076117771df82e7f1b023e68c2adc3d9ebf0a288132f0"}
successor.AU_ID = "c52ab6db-176e-4378-ac88-2ee1bfc58487"
successor.AU_GENERATION = "477c3f92-06f0-4dae-9445-ce6d09c3f462"
successor.DETACH = "48e4d856-6652-4903-af9f-49bf4774bc0d"
successor.DETACH_HASH = "sha256:6302314b46ee2699d9a05ef8552df2932fccb385f29a3442eba64c26458ad1b2"
successor.KEY = "a0v-qyh-clean-generation-bh-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 8
successor.PREDECESSOR_EXECUTION_EPOCH = 4
successor.PREDECESSOR_ROUTE_REVISION = 149
successor.PREDECESSOR_GROUP_REVISION = 176
successor.replacement_module = lambda: bh_replacement.replacement

BH_ID = successor.AV_ID
BH_GENERATION = successor.AV_GENERATION
AV_ID = BH_ID
AV_GENERATION = BH_GENERATION
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
    return {**result, "outcome": "CURRENT_BH_SUCCESSOR_REGISTERED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preview", "register"])
    args = parser.parse_args()
    plane = setup()
    request = current_request()
    result = ({"outcome": "CURRENT_BH_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()} if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

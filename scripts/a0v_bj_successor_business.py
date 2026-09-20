#!/usr/bin/env python3
"""Register BJ directly from the exact detached BI authority."""
from __future__ import annotations

import argparse
import json

import a0v_av_successor_business as successor
import a0v_bj_replacement_recovery as bj_replacement


successor.STATE = bj_replacement.replacement.STATE / "registration-bj"
successor.AV_ID = "2c3972b1-67c1-400d-aa63-b90de369f5de"
successor.AV_GENERATION = "8dafd4ae-d42b-4f2f-accb-b5a49e7c9a3b"
successor.LOCK = "sha256:d01e0d465ac65672a7edac4be6b453d16958037d15fff75220b6d5dee4458128"
successor.CONFIG = {"configurationId": "552451f8-f585-42b5-a992-7a366aaca1be", "revision": 1,
                    "hash": "sha256:bf55da36296ed24bb71e29d3a95639580239ef449ed36ab4edecac9e4f1d0a5d"}
successor.AU_ID = "8ca245a1-8420-4590-b9e4-f92256fc22ce"
successor.AU_GENERATION = "6f527122-a4a5-4056-a4e6-ca888f4b64d7"
successor.DETACH = "64375b18-389a-4e5b-bd17-c7e03a63edd6"
successor.DETACH_HASH = "sha256:0962da63b333d3bf94ea9cd9272e2aeba8afad44e3c678c560b4bd4872b56ddd"
successor.KEY = "a0v-qyh-clean-generation-bj-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 8
successor.PREDECESSOR_EXECUTION_EPOCH = 4
successor.PREDECESSOR_ROUTE_REVISION = 155
successor.PREDECESSOR_GROUP_REVISION = 182
successor.replacement_module = lambda: bj_replacement.replacement

BJ_ID = successor.AV_ID
BJ_GENERATION = successor.AV_GENERATION
AV_ID = BJ_ID
AV_GENERATION = BJ_GENERATION
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
    return {**result, "outcome": "CURRENT_BJ_SUCCESSOR_REGISTERED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preview", "register"])
    args = parser.parse_args()
    plane = setup()
    request = current_request()
    result = ({"outcome": "CURRENT_BJ_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()} if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

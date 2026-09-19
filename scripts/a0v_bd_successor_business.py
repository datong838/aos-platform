#!/usr/bin/env python3
"""Register BD directly from the exact BC detach authority."""
from __future__ import annotations

import argparse
import json

import a0v_av_successor_business as successor
import a0v_bd_replacement_recovery as bd_replacement


successor.STATE = bd_replacement.replacement.STATE / "registration-bd"
successor.AV_ID = "c2d6ef97-30ec-4980-9421-54a899607853"
successor.AV_GENERATION = "f5e01f1d-e6c5-425a-9145-6f7a82ec65e5"
successor.LOCK = "sha256:0acab1c9950e014737c8e5814750bca0118bf265e9dfeb382a52d32b45a71547"
successor.CONFIG = {"configurationId": "2c19490b-b82f-48d4-b035-00c2824a6d7a", "revision": 1,
                    "hash": "sha256:678f6104653a499b05610e5272a96200bf35fbefba8a5804c5896e597ea531b3"}
successor.AU_ID = "3b895c30-34ca-4710-b978-02645d49c83a"
successor.AU_GENERATION = "31776dcd-e28f-4b6d-ae45-75fb0ab5a505"
successor.DETACH = "39bb3f98-78b6-444b-9d5c-a51991b03f42"
successor.DETACH_HASH = "sha256:7351a8aca2751c721b96ef1c72352318a507a18598930e13fbc79667f3bc169c"
successor.KEY = "a0v-qyh-clean-generation-bd-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 8
successor.PREDECESSOR_EXECUTION_EPOCH = 4
successor.PREDECESSOR_ROUTE_REVISION = 137
successor.PREDECESSOR_GROUP_REVISION = 164
successor.replacement_module = lambda: bd_replacement.replacement

BD_ID = successor.AV_ID
BD_GENERATION = successor.AV_GENERATION
AV_ID = BD_ID
AV_GENERATION = BD_GENERATION
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
    return {**result, "outcome": "CURRENT_BD_SUCCESSOR_REGISTERED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preview", "register"])
    args = parser.parse_args()
    plane = setup()
    request = current_request()
    result = ({"outcome": "CURRENT_BD_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()} if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

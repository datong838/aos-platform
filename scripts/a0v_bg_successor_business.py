#!/usr/bin/env python3
"""Register BG directly from the exact detached BF authority."""
from __future__ import annotations

import argparse
import json

import a0v_av_successor_business as successor
import a0v_bg_replacement_recovery as bg_replacement


successor.STATE = bg_replacement.replacement.STATE / "registration-bg"
successor.AV_ID = "c52ab6db-176e-4378-ac88-2ee1bfc58487"
successor.AV_GENERATION = "477c3f92-06f0-4dae-9445-ce6d09c3f462"
successor.LOCK = "sha256:0e1880beeac4b28399b828c79b387c32e0be1cc41e982f786a8ddd8d04f88eb3"
successor.CONFIG = {"configurationId": "1f1e5dde-a380-4670-9fbb-d70915d74883", "revision": 1,
                    "hash": "sha256:cd357bdd8b0df9f9e65ff9d800f8da5b638e48031fb738ecef9661c32b17269e"}
successor.AU_ID = "98a16beb-6342-48bd-9e12-989f3612ca00"
successor.AU_GENERATION = "e33e0a9e-7296-4374-9aa9-113f1ed79b5f"
successor.DETACH = "03852ebe-20e0-4a41-a5fc-c9eb3aa927dd"
successor.DETACH_HASH = "sha256:ff354c79889453d270baa1b722abdb8785493f7f9432aa42fbe5b6ac7a61c925"
successor.KEY = "a0v-qyh-clean-generation-bg-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 8
successor.PREDECESSOR_EXECUTION_EPOCH = 4
successor.PREDECESSOR_ROUTE_REVISION = 146
successor.PREDECESSOR_GROUP_REVISION = 173
successor.replacement_module = lambda: bg_replacement.replacement

BG_ID = successor.AV_ID
BG_GENERATION = successor.AV_GENERATION
AV_ID = BG_ID
AV_GENERATION = BG_GENERATION
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
    return {**result, "outcome": "CURRENT_BG_SUCCESSOR_REGISTERED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preview", "register"])
    args = parser.parse_args()
    plane = setup()
    request = current_request()
    result = ({"outcome": "CURRENT_BG_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()} if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

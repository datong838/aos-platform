#!/usr/bin/env python3
"""Register BL directly from the exact detached BK authority."""
from __future__ import annotations

import argparse
import json

import a0v_av_successor_business as successor
import a0v_bl_replacement_recovery as bl_replacement


successor.STATE = bl_replacement.replacement.STATE / "registration-bl"
successor.AV_ID = "ac9b3ec8-68ad-4e05-9f30-b2f8f6a473bc"
successor.AV_GENERATION = "116d12fc-93bc-4071-a973-fdc6830ea8b1"
successor.LOCK = "sha256:47af46b5658b7952f9d3068466ba06c6203e51fef899c5d661026230893b334e"
successor.CONFIG = {"configurationId": "1d25aa72-86b9-4d5a-8523-0e4a4a013a71", "revision": 1,
                    "hash": "sha256:4f85fd85b307b20ed1065a774e0af26e7692754bf14d47f8d5430d74c083cf9a"}
successor.AU_ID = "8c78f903-ebd8-4589-97a0-afad76e209e0"
successor.AU_GENERATION = "9ea4ba9d-1ef8-45a6-9060-1e4f37c87038"
successor.DETACH = "dfce56ec-4bff-4793-a5d5-dab4ad45aa1c"
successor.DETACH_HASH = "sha256:3fc2b8a9c3614912b1ac7a9c0d127677f3cc0187ed5c24209da10a963c71dca4"
successor.KEY = "a0v-qyh-clean-generation-bl-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 8
successor.PREDECESSOR_EXECUTION_EPOCH = 4
successor.PREDECESSOR_ROUTE_REVISION = 161
successor.PREDECESSOR_GROUP_REVISION = 188
successor.replacement_module = lambda: bl_replacement.replacement

BL_ID = successor.AV_ID
BL_GENERATION = successor.AV_GENERATION
AV_ID = BL_ID
AV_GENERATION = BL_GENERATION
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
    return {**result, "outcome": "CURRENT_BL_SUCCESSOR_REGISTERED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preview", "register"])
    args = parser.parse_args()
    plane = setup()
    request = current_request()
    result = ({"outcome": "CURRENT_BL_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()} if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

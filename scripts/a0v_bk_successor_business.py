#!/usr/bin/env python3
"""Register BK directly from the exact detached BJ authority."""
from __future__ import annotations

import argparse
import json

import a0v_av_successor_business as successor
import a0v_bk_replacement_recovery as bk_replacement


successor.STATE = bk_replacement.replacement.STATE / "registration-bk"
successor.AV_ID = "8c78f903-ebd8-4589-97a0-afad76e209e0"
successor.AV_GENERATION = "9ea4ba9d-1ef8-45a6-9060-1e4f37c87038"
successor.LOCK = "sha256:462bc93fcd577556199e60c70eb21b3e5ae539b310f101aeb6095b9613babf71"
successor.CONFIG = {"configurationId": "47ba0191-fb87-4df0-a8f2-58ca17579c05", "revision": 1,
                    "hash": "sha256:ffe36da2bc248d648e78a8585fd22c3ea8d991dff5b0e03200f49fa13a6391ee"}
successor.AU_ID = "2c3972b1-67c1-400d-aa63-b90de369f5de"
successor.AU_GENERATION = "8dafd4ae-d42b-4f2f-accb-b5a49e7c9a3b"
successor.DETACH = "2c5d28d5-cfcc-474d-827d-d0031d0de4d8"
successor.DETACH_HASH = "sha256:9fff94f0bc18f763292002f838bb0f197e9548e59eefe92d2722cd71d307281d"
successor.KEY = "a0v-qyh-clean-generation-bk-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 8
successor.PREDECESSOR_EXECUTION_EPOCH = 4
successor.PREDECESSOR_ROUTE_REVISION = 158
successor.PREDECESSOR_GROUP_REVISION = 185
successor.replacement_module = lambda: bk_replacement.replacement

BK_ID = successor.AV_ID
BK_GENERATION = successor.AV_GENERATION
AV_ID = BK_ID
AV_GENERATION = BK_GENERATION
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
    return {**result, "outcome": "CURRENT_BK_SUCCESSOR_REGISTERED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preview", "register"])
    args = parser.parse_args()
    plane = setup()
    request = current_request()
    result = ({"outcome": "CURRENT_BK_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()} if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

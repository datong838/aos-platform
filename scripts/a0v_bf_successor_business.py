#!/usr/bin/env python3
"""Register BF directly from the exact detached BE authority."""
from __future__ import annotations

import argparse
import json

import a0v_av_successor_business as successor
import a0v_bf_replacement_recovery as bf_replacement


successor.STATE = bf_replacement.replacement.STATE / "registration-bf"
successor.AV_ID = "98a16beb-6342-48bd-9e12-989f3612ca00"
successor.AV_GENERATION = "e33e0a9e-7296-4374-9aa9-113f1ed79b5f"
successor.LOCK = "sha256:6cb2cef564ead4ace9dbeb091512b4f6cf0d8a8508782308a8cacea89bc921ed"
successor.CONFIG = {"configurationId": "f32f4a2e-e867-4504-92c5-1355f1e7d895", "revision": 1,
                    "hash": "sha256:fe5e9dc20756fe9f38e04b5563aab77909b78721bab823af3777712a2db89657"}
successor.AU_ID = "1a0f801f-d8f3-43af-a31e-5c9fc8161d6d"
successor.AU_GENERATION = "93349d9b-ad61-4919-9cbd-e1e9b02545bb"
successor.DETACH = "2b758ca2-8afd-48a4-af23-6367fe505758"
successor.DETACH_HASH = "sha256:db4450919ba39f8443aa20eb0a8b0d9be27eda5a17c40a069b17a0637e91651d"
successor.KEY = "a0v-qyh-clean-generation-bf-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 8
successor.PREDECESSOR_EXECUTION_EPOCH = 4
successor.PREDECESSOR_ROUTE_REVISION = 143
successor.PREDECESSOR_GROUP_REVISION = 170
successor.replacement_module = lambda: bf_replacement.replacement

BF_ID = successor.AV_ID
BF_GENERATION = successor.AV_GENERATION
AV_ID = BF_ID
AV_GENERATION = BF_GENERATION
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
    return {**result, "outcome": "CURRENT_BF_SUCCESSOR_REGISTERED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preview", "register"])
    args = parser.parse_args()
    plane = setup()
    request = current_request()
    result = ({"outcome": "CURRENT_BF_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()} if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

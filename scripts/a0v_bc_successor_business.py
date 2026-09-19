#!/usr/bin/env python3
"""Register BC directly from the exact BB detach authority."""
from __future__ import annotations

import argparse
import json

import a0v_av_successor_business as successor
import a0v_bc_replacement_recovery as bc_replacement


successor.STATE = bc_replacement.replacement.STATE / "registration-bc"
successor.AV_ID = "3b895c30-34ca-4710-b978-02645d49c83a"
successor.AV_GENERATION = "31776dcd-e28f-4b6d-ae45-75fb0ab5a505"
successor.LOCK = "sha256:c59c7f036bb2a5e2892e854a79d1baca5b6ca915a191e7376812de9de54106a6"
successor.CONFIG = {"configurationId": "ab882e96-733c-43ac-b792-520090082595", "revision": 1,
                    "hash": "sha256:0b5c271d1c0ffb4ca18f1e0c5a00821fe4a6e15bab79236b0ffa8971e2793ab1"}
successor.AU_ID = "09752ccf-d51a-44b7-a5bf-62b5ab8ec5d6"
successor.AU_GENERATION = "099c4d17-47fb-4c07-9ef1-c627ca7b4239"
successor.DETACH = "0dd16596-c66b-4390-b9dc-0504c1a822c7"
successor.DETACH_HASH = "sha256:023f817fd9c924b05ec59ce011451cef0364061956e8c156cadbc7dfcde73a6a"
successor.KEY = "a0v-qyh-clean-generation-bc-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 8
successor.PREDECESSOR_EXECUTION_EPOCH = 4
successor.PREDECESSOR_ROUTE_REVISION = 134
successor.PREDECESSOR_GROUP_REVISION = 161
successor.replacement_module = lambda: bc_replacement.replacement

BC_ID = successor.AV_ID
BC_GENERATION = successor.AV_GENERATION
AV_ID = BC_ID
AV_GENERATION = BC_GENERATION
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
    return {**result, "outcome": "CURRENT_BC_SUCCESSOR_REGISTERED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preview", "register"])
    args = parser.parse_args()
    plane = setup()
    request = current_request()
    result = ({"outcome": "CURRENT_BC_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()} if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

#!/usr/bin/env python3
"""Register BB directly from the exact BA detach authority."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_av_successor_business as successor
import a0v_bb_replacement_recovery as bb_replacement


ROOT = Path(__file__).resolve().parents[1]
successor.STATE = bb_replacement.replacement.STATE / "registration-bb"
successor.AV_ID = "09752ccf-d51a-44b7-a5bf-62b5ab8ec5d6"
successor.AV_GENERATION = "099c4d17-47fb-4c07-9ef1-c627ca7b4239"
successor.LOCK = "sha256:f5ae36a5e7db006f81b87af036c5e83b6a3ed7f0f714182b15b598cd9f03fe37"
successor.CONFIG = {"configurationId": "f29dd7df-2840-45c0-8500-3deb36845fac", "revision": 1,
                    "hash": "sha256:3075c62171d85a2b0dc65fe650e53a3c44f2fa1f62af82abc27a8ece2053fadb"}
successor.AU_ID = "9110f69b-bb31-4d17-98e8-6c5ed1d9234f"
successor.AU_GENERATION = "197f5036-656a-4b58-a261-e93e2fffea18"
successor.DETACH = "707b4a88-2823-4368-81c6-5e5525c3ea48"
successor.DETACH_HASH = "sha256:f3df39ef131deb553919a66c8fe2d4056ef096a4537447472f300e2936a941b5"
successor.KEY = "a0v-qyh-clean-generation-bb-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 8
successor.PREDECESSOR_EXECUTION_EPOCH = 4
successor.PREDECESSOR_ROUTE_REVISION = 131
successor.PREDECESSOR_GROUP_REVISION = 158
successor.replacement_module = lambda: bb_replacement.replacement

BB_ID = successor.AV_ID
BB_GENERATION = successor.AV_GENERATION
AV_ID = BB_ID
AV_GENERATION = BB_GENERATION
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
    return {**result, "outcome": "CURRENT_BB_SUCCESSOR_REGISTERED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preview", "register"])
    args = parser.parse_args()
    plane = setup()
    request = current_request()
    result = ({"outcome": "CURRENT_BB_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()} if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

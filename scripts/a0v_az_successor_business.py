#!/usr/bin/env python3
"""Register AZ from AX detach after AY's configured-unactivated retirement."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_av_successor_business as successor
import a0v_az_replacement_recovery as az_replacement


ROOT = Path(__file__).resolve().parents[1]
successor.STATE = az_replacement.replacement.STATE / "registration-az"
successor.AV_ID = "40eee6d9-fb03-4657-a83e-aeb38ec4aeeb"
successor.AV_GENERATION = "7b6befaa-2f92-4e62-85f9-0ca060ec4b90"
successor.LOCK = "sha256:7826b7400df634c9ad5f538b7db24026fc8930ee4bf6627b5d13277b2fa6afc5"
successor.CONFIG = {"configurationId": "643a2461-6481-48bf-8f17-df2e8789d169", "revision": 1,
                    "hash": "sha256:8564b723a3d6e3f62f7f6f8095c6d17081283764fce549b2b549b6239e0ef49b"}
successor.AU_ID = "be884663-0dba-4d9b-aa56-84caaf01147d"
successor.AU_GENERATION = "a14c911b-6796-4d22-a3b0-1817cf502de9"
successor.DETACH = "622c8e25-ec0f-40dd-bf1f-ea57d180a800"
successor.DETACH_HASH = "sha256:583954da94992d30f7c5f9133c235eb3b17e0d8d190c27d61fe47621d41a6870"
successor.KEY = "a0v-qyh-clean-generation-az-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 8
successor.PREDECESSOR_EXECUTION_EPOCH = 4
successor.PREDECESSOR_ROUTE_REVISION = 125
successor.PREDECESSOR_GROUP_REVISION = 152
successor.replacement_module = lambda: az_replacement.replacement

AZ_ID = successor.AV_ID
AZ_GENERATION = successor.AV_GENERATION
AV_ID = AZ_ID
AV_GENERATION = AZ_GENERATION
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
    return {**result, "outcome": "CURRENT_AZ_SUCCESSOR_REGISTERED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preview", "register"])
    args = parser.parse_args()
    plane = setup()
    request = current_request()
    result = ({"outcome": "CURRENT_AZ_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()} if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

#!/usr/bin/env python3
"""Register AY from AX's exact detach receipt after replacement enable."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_av_successor_business as successor
import a0v_ay_replacement_recovery as ay_replacement


ROOT = Path(__file__).resolve().parents[1]
successor.STATE = ay_replacement.replacement.STATE / "registration-ay"
successor.AV_ID = "81df994f-23ce-4448-ac46-366aaee63924"
successor.AV_GENERATION = "a1069f60-46f5-41a8-bd18-61ed677eb3bd"
successor.LOCK = "sha256:7826b7400df634c9ad5f538b7db24026fc8930ee4bf6627b5d13277b2fa6afc5"
successor.CONFIG = {"configurationId": "ce24590a-479e-4a5e-94ab-01d138e0675c", "revision": 1,
                    "hash": "sha256:579a652e471f626f08e25f80f19b4e9f77b91531a456dac87ef2f2220e1cff89"}
successor.AU_ID = "be884663-0dba-4d9b-aa56-84caaf01147d"
successor.AU_GENERATION = "a14c911b-6796-4d22-a3b0-1817cf502de9"
successor.DETACH = "622c8e25-ec0f-40dd-bf1f-ea57d180a800"
successor.DETACH_HASH = "sha256:583954da94992d30f7c5f9133c235eb3b17e0d8d190c27d61fe47621d41a6870"
successor.KEY = "a0v-qyh-clean-generation-ay-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 8
successor.PREDECESSOR_EXECUTION_EPOCH = 4
successor.PREDECESSOR_ROUTE_REVISION = 125
successor.PREDECESSOR_GROUP_REVISION = 152
successor.replacement_module = lambda: ay_replacement.replacement

AY_ID = successor.AV_ID
AY_GENERATION = successor.AV_GENERATION
AV_ID = AY_ID
AV_GENERATION = AY_GENERATION
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
    return {**result, "outcome": "CURRENT_AY_SUCCESSOR_REGISTERED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preview", "register"])
    args = parser.parse_args()
    plane = setup()
    request = current_request()
    result = ({"outcome": "CURRENT_AY_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()} if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

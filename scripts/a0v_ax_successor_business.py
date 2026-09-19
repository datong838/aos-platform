#!/usr/bin/env python3
"""Register AX from AW's exact detach receipt after replacement enable."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_av_successor_business as successor
import a0v_ax_replacement_recovery as ax_replacement


ROOT = Path(__file__).resolve().parents[1]
successor.STATE = ax_replacement.replacement.STATE / "registration-ax"
successor.AV_ID = "be884663-0dba-4d9b-aa56-84caaf01147d"
successor.AV_GENERATION = "a14c911b-6796-4d22-a3b0-1817cf502de9"
successor.LOCK = "sha256:ae0c890abf2629daa136a615d9eadc4796e544f2e728ab4f567f0e7ebf65adc5"
successor.CONFIG = {"configurationId": "0e59aa44-bda5-43db-930d-b77bb7b02d32", "revision": 1,
                    "hash": "sha256:f2ed99032b03af6f2855b39e513ad5117fc1fdd2797927c77d9f4d485fda9bb2"}
successor.AU_ID = "f94b9425-9bc4-4369-8ae3-138c50c9ab81"
successor.AU_GENERATION = "a92f7bb2-3d90-4d88-9632-5fc9a70bd650"
successor.DETACH = "0c50775b-62fe-4251-81f4-3c9a8709a90e"
successor.DETACH_HASH = "sha256:22b3fbf13e9fb92d3f7a4744a5f2787c9b0d3adf216727ed01439f1cb18d9226"
successor.KEY = "a0v-qyh-clean-generation-ax-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 11
successor.PREDECESSOR_EXECUTION_EPOCH = 6
successor.PREDECESSOR_ROUTE_REVISION = 122
successor.PREDECESSOR_GROUP_REVISION = 149
successor.replacement_module = lambda: ax_replacement.replacement

AX_ID = successor.AV_ID
AX_GENERATION = successor.AV_GENERATION
AV_ID = AX_ID
AV_GENERATION = AX_GENERATION
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
    return {**result, "outcome": "CURRENT_AX_SUCCESSOR_REGISTERED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preview", "register"])
    args = parser.parse_args()
    plane = setup()
    request = current_request()
    result = ({"outcome": "CURRENT_AX_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()} if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

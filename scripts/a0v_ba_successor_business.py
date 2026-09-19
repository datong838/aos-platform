#!/usr/bin/env python3
"""Register BA directly from the exact AZ detach authority."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_av_successor_business as successor
import a0v_ba_replacement_recovery as ba_replacement


ROOT = Path(__file__).resolve().parents[1]
successor.STATE = ba_replacement.replacement.STATE / "registration-ba"
successor.AV_ID = "9110f69b-bb31-4d17-98e8-6c5ed1d9234f"
successor.AV_GENERATION = "197f5036-656a-4b58-a261-e93e2fffea18"
successor.LOCK = "sha256:6fc165d534435f39488e59c47d615501c1b011beadb59a4a92ed1de76d769757"
successor.CONFIG = {"configurationId": "2dbe3f41-67b6-4ac6-b84e-b05d01392080", "revision": 1,
                    "hash": "sha256:6902d87b35a0d6d303083abfc29e375a3e3cdd2f38a3123eff1e5c5109608de2"}
successor.AU_ID = "40eee6d9-fb03-4657-a83e-aeb38ec4aeeb"
successor.AU_GENERATION = "7b6befaa-2f92-4e62-85f9-0ca060ec4b90"
successor.DETACH = "ee221609-d3d5-4227-8382-063d2ca0eab2"
successor.DETACH_HASH = "sha256:36b32dccacc9b7f8e78579fac44db423fe3ab470bc5165e205bf268c4cab8a7c"
successor.KEY = "a0v-qyh-clean-generation-ba-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 8
successor.PREDECESSOR_EXECUTION_EPOCH = 4
successor.PREDECESSOR_ROUTE_REVISION = 128
successor.PREDECESSOR_GROUP_REVISION = 155
successor.replacement_module = lambda: ba_replacement.replacement

BA_ID = successor.AV_ID
BA_GENERATION = successor.AV_GENERATION
AV_ID = BA_ID
AV_GENERATION = BA_GENERATION
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
    return {**result, "outcome": "CURRENT_BA_SUCCESSOR_REGISTERED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preview", "register"])
    args = parser.parse_args()
    plane = setup()
    request = current_request()
    result = ({"outcome": "CURRENT_BA_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()} if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

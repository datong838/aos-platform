#!/usr/bin/env python3
"""Register DR directly from the exact detached DQ authority."""
from __future__ import annotations

import argparse
import json
import os

import a0v_dq_successor_business as dq_successor
import a0v_dr_replacement_recovery as dr_recovery

# 复用 dq_successor 的注册通道（a0v_av_successor_business 模板），换成 DR 身份
successor = dq_successor.successor

successor.STATE = dr_recovery.replacement.STATE / "registration-dr"
successor.AV_ID = "89975129-7e0f-4860-ac56-7a031ebe4a1a"
successor.AV_GENERATION = "c78b2e2e-57ef-47ad-be07-9acf689e578c"
successor.LOCK = "sha256:4c6cac4b1a57d78954252585e373380b219c40bd20f0b7e39b5b04cf1df15cf2"
successor.CONFIG = {"configurationId": "e4b10c10-1801-40bd-a9d4-46e42d5b4b31", "revision": 1,
                    "hash": "sha256:82e1f59fa2365b5eb0f4c61187fa47133465a91f793f1df0435ef236d45e747f"}
successor.AU_ID = "29e553b2-3afc-4b15-b860-f79104f3491a"
successor.AU_GENERATION = "b8d6900d-b4a3-43d8-8891-a4b1d02abd3c"
successor.DETACH = "fa1e39dd-4bfe-4647-b0cd-ed3e3059f65c"
successor.DETACH_HASH = "sha256:7cd61ec62e9d394c8eba3e61693c2570763c05f687b717a3b51ab3fca96a96a4"
successor.KEY = "a0v-qyh-clean-generation-dr-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 332
successor.PREDECESSOR_GROUP_REVISION = 359
successor.replacement_module = lambda: dr_recovery.replacement

DR_ID = successor.AV_ID
DR_GENERATION = successor.AV_GENERATION
GROUP = successor.GROUP
ACTOR = successor.ACTOR
STATE = successor.STATE


def setup():
    return dq_successor.setup()


def run(mode: str) -> dict:
    plane = setup()
    if mode == "preview":
        request = successor.current_request()
        return {"outcome": "CURRENT_DR_SUCCESSOR_REQUEST_PREVIEW",
                "request": request.model_dump(mode="json", by_alias=True),
                "requestHash": request.request_hash()}
    result = successor.register(plane, successor.current_request())
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "DR_").replace("DQ_", "DR_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preview", "register"])
    args = parser.parse_args()
    print(json.dumps(run(args.mode), ensure_ascii=False, default=str, indent=2))

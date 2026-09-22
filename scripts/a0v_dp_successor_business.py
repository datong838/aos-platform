#!/usr/bin/env python3
"""Register DP directly from the exact detached DO authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_dp_replacement_recovery as dp_replacement


successor.STATE = dp_replacement.replacement.STATE / "registration-dp"
successor.AV_ID = "d2d3c478-f9d9-4489-92b7-1de57f546452"
successor.AV_GENERATION = "b15f1733-89dd-4684-9475-9fba095a1d74"
successor.LOCK = "sha256:06c2ac6eded4cadd0ffa0edb9bbbad3bac59d36e9f42993f6e6ecb5a7c44adba"
successor.CONFIG = {"configurationId": "5f9ceec4-8532-44be-bb07-13617e195f70", "revision": 1,
                    "hash": "sha256:ffef5daa927083eddc12d3f5848efb7c2a818bb1b631905a61e0ef913b18ceab"}
successor.AU_ID = "e748c240-f9d4-47c0-a9dc-3c473b311cae"
successor.AU_GENERATION = "93b514ad-3920-4eb4-8fc7-7cb1106254ff"
successor.DETACH = "ad02a6ad-7fa6-45fc-a200-ad63629fd7bf"
successor.DETACH_HASH = "sha256:7deae31d1e7793e17d8fd18673ad02f2e0c08a6b9514604636779ee7f3c20c1c"
successor.KEY = "a0v-qyh-clean-generation-dp-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 326
successor.PREDECESSOR_GROUP_REVISION = 353
successor.replacement_module = lambda: dp_replacement.replacement

DP_ID = successor.AV_ID
DP_GENERATION = successor.AV_GENERATION
AV_ID = DP_ID
AV_GENERATION = DP_GENERATION
LOCK = successor.LOCK
CONFIG = successor.CONFIG
GROUP = successor.GROUP
KEY = successor.KEY
ACTOR = successor.ACTOR
STATE = successor.STATE


def setup():
    import a0v_event_complete_product_api as product_api
    original_load_launcher = product_api.load_launcher

    def load_launcher():
        launcher = original_load_launcher()
        launcher.DEFAULT_CREDENTIALS = dp_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = dp_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = dp_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_dp():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                dp_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_dp
        return launcher

    product_api.load_launcher = load_launcher
    return successor.setup()


def run(mode: str) -> dict:
    plane = setup()
    if mode == "preview":
        request = successor.current_request()
        return {"outcome": "CURRENT_DP_SUCCESSOR_REQUEST_PREVIEW",
                "request": request.model_dump(mode="json", by_alias=True),
                "requestHash": request.request_hash()}
    result = successor.register(plane, successor.current_request())
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "DP_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preview", "register"])
    args = parser.parse_args()
    print(json.dumps(run(args.mode), ensure_ascii=False, default=str, indent=2))

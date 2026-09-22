#!/usr/bin/env python3
"""Register DQ directly from the exact detached DP authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_dq_replacement_recovery as dq_replacement


successor.STATE = dq_replacement.replacement.STATE / "registration-dq"
successor.AV_ID = "29e553b2-3afc-4b15-b860-f79104f3491a"
successor.AV_GENERATION = "b8d6900d-b4a3-43d8-8891-a4b1d02abd3c"
successor.LOCK = "sha256:0adb9ab736b270a430f148b28d1ce57c556375219b34ef733b909d9cfdaa1d63"
successor.CONFIG = {"configurationId": "2653bddb-a5cb-4cea-8b36-2a76920374fd", "revision": 1,
                    "hash": "sha256:10843bf51b5eb5a1c9ce39e3ed30881b1c9661d87cddab3f52898f7ec3ae2900"}
successor.AU_ID = "d2d3c478-f9d9-4489-92b7-1de57f546452"
successor.AU_GENERATION = "b15f1733-89dd-4684-9475-9fba095a1d74"
successor.DETACH = "b37d6076-1817-4617-9180-469d2e243273"
successor.DETACH_HASH = "sha256:600443ffed027de00432d61c0fbe412613d75d80cd47fa9950eaa3b8d18ac8ee"
successor.KEY = "a0v-qyh-clean-generation-dq-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 329
successor.PREDECESSOR_GROUP_REVISION = 356
successor.replacement_module = lambda: dq_replacement.replacement

DQ_ID = successor.AV_ID
DQ_GENERATION = successor.AV_GENERATION
AV_ID = DQ_ID
AV_GENERATION = DQ_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = dq_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = dq_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = dq_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_dq():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                dq_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_dq
        return launcher

    product_api.load_launcher = load_launcher
    return successor.setup()


def run(mode: str) -> dict:
    plane = setup()
    if mode == "preview":
        request = successor.current_request()
        return {"outcome": "CURRENT_DQ_SUCCESSOR_REQUEST_PREVIEW",
                "request": request.model_dump(mode="json", by_alias=True),
                "requestHash": request.request_hash()}
    result = successor.register(plane, successor.current_request())
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "DQ_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preview", "register"])
    args = parser.parse_args()
    print(json.dumps(run(args.mode), ensure_ascii=False, default=str, indent=2))

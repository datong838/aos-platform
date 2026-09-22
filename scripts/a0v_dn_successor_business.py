#!/usr/bin/env python3
"""Register DN directly from the exact detached DM authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_dn_replacement_recovery as dn_replacement


successor.STATE = dn_replacement.replacement.STATE / "registration-dn"
successor.AV_ID = "2cb67f0a-0970-4d75-9c4a-a19d68563a3e"
successor.AV_GENERATION = "e8b25248-98fc-475b-bf9e-1e7e3e803ec7"
successor.LOCK = "sha256:ddc55f6f4f7b5ccb6729b983df4ec98895d99642fbdaf349e61cccf83c26e4a4"
successor.CONFIG = {"configurationId": "b3b76d74-c526-4147-839c-c21902931649", "revision": 1,
                    "hash": "sha256:b1c846f6550199aa2d1701098013ee59f42085e5085ce8c9ede6556d2cdbbeff"}
successor.AU_ID = "5103c27a-753e-4cad-85cb-9fa35dc0574d"
successor.AU_GENERATION = "4da719c7-1144-4867-bbdc-8a70362ba5f0"
successor.DETACH = "cf7a8c88-8ce1-41c7-bbc0-3fd0263b53ac"
successor.DETACH_HASH = "sha256:286b64b99a46f7b627370e65ca95f5394477d63d185447192757b2b16f31f6ae"
successor.KEY = "a0v-qyh-clean-generation-dn-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 320
successor.PREDECESSOR_GROUP_REVISION = 347
successor.replacement_module = lambda: dn_replacement.replacement

DN_ID = successor.AV_ID
DN_GENERATION = successor.AV_GENERATION
AV_ID = DN_ID
AV_GENERATION = DN_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = dn_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = dn_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = dn_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_dn():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                dn_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_dn
        return launcher

    product_api.load_launcher = load_launcher
    return successor.setup()


def run(mode: str) -> dict:
    plane = setup()
    if mode == "preview":
        request = successor.current_request()
        return {"outcome": "CURRENT_DN_SUCCESSOR_REQUEST_PREVIEW",
                "request": request.model_dump(mode="json", by_alias=True),
                "requestHash": request.request_hash()}
    result = successor.register(plane, successor.current_request())
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "DN_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preview", "register"])
    args = parser.parse_args()
    print(json.dumps(run(args.mode), ensure_ascii=False, default=str, indent=2))

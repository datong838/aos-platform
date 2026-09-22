#!/usr/bin/env python3
"""Register DO directly from the exact detached DN authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_do_replacement_recovery as do_replacement


successor.STATE = do_replacement.replacement.STATE / "registration-do"
successor.AV_ID = "e748c240-f9d4-47c0-a9dc-3c473b311cae"
successor.AV_GENERATION = "93b514ad-3920-4eb4-8fc7-7cb1106254ff"
successor.LOCK = "sha256:7a5f02619ee98dec6aa96784e64b2024b7d988ded5e0d76b4fefe9b35894a3e6"
successor.CONFIG = {"configurationId": "0a1ef242-3dae-456d-bc8a-3975e771bae4", "revision": 1,
                    "hash": "sha256:d445eec67e68cb4c0d0130f5d1984106d5d0fc0b0a82c7868263471f13b79bd1"}
successor.AU_ID = "2cb67f0a-0970-4d75-9c4a-a19d68563a3e"
successor.AU_GENERATION = "e8b25248-98fc-475b-bf9e-1e7e3e803ec7"
successor.DETACH = "35a465a7-ef65-479d-9534-9850a82044b6"
successor.DETACH_HASH = "sha256:8adfdd0dbe1bdb14c09649f1255f532fc7628bc6414c98ede5e5f2022f2e34a8"
successor.KEY = "a0v-qyh-clean-generation-do-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 323
successor.PREDECESSOR_GROUP_REVISION = 350
successor.replacement_module = lambda: do_replacement.replacement

DO_ID = successor.AV_ID
DO_GENERATION = successor.AV_GENERATION
AV_ID = DO_ID
AV_GENERATION = DO_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = do_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = do_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = do_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_do():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                do_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_do
        return launcher

    product_api.load_launcher = load_launcher
    return successor.setup()


def run(mode: str) -> dict:
    plane = setup()
    if mode == "preview":
        request = successor.current_request()
        return {"outcome": "CURRENT_DO_SUCCESSOR_REQUEST_PREVIEW",
                "request": request.model_dump(mode="json", by_alias=True),
                "requestHash": request.request_hash()}
    result = successor.register(plane, successor.current_request())
    return {**result, "outcome": result.get("outcome", "").replace("AV_", "DO_")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preview", "register"])
    args = parser.parse_args()
    print(json.dumps(run(args.mode), ensure_ascii=False, default=str, indent=2))

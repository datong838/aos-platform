#!/usr/bin/env python3
"""Register BW directly from the exact detached BV authority."""
from __future__ import annotations

import argparse
import json
import os

import a0v_av_successor_business as successor
import a0v_bw_replacement_recovery as bw_replacement


successor.STATE = bw_replacement.replacement.STATE / "registration-bw"
successor.AV_ID = "9b6e1277-a0a2-447d-9062-a98adfed3f22"
successor.AV_GENERATION = "62cf014b-9ce5-4512-8a34-b55a79e053c3"
successor.LOCK = "sha256:5b2392496ba942a535260209dcf681030dd00b58765bf4983622d4af0be49ee0"
successor.CONFIG = {"configurationId": "99d47eef-7b92-4cf8-aa40-0f7056bbb9ca", "revision": 1,
                    "hash": "sha256:27cf74ba5a8643ea91e31f1e540c18b12614df71dae98fd34ca5a39c51039b84"}
successor.AU_ID = "2b1aa826-b595-40d4-aeb2-9a7ce9d33c36"
successor.AU_GENERATION = "e8a5b32b-9a29-41bf-9c7f-87c7cd96b359"
successor.DETACH = "76145710-3ec6-4271-a8b7-248e045645f7"
successor.DETACH_HASH = "sha256:dc20911dba0fe1792b1a881f215109d8bf6f4db2754bdf12d3cc3fdab0e58608"
successor.KEY = "a0v-qyh-clean-generation-bw-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 191
successor.PREDECESSOR_GROUP_REVISION = 218
successor.replacement_module = lambda: bw_replacement.replacement

BW_ID = successor.AV_ID
BW_GENERATION = successor.AV_GENERATION
AV_ID = BW_ID
AV_GENERATION = BW_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = bw_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = bw_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = bw_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_bw():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                bw_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_bw
        return launcher

    product_api.load_launcher = load_launcher
    return successor.setup()


def current_request():
    return successor.current_request()


def register(plane, request):
    from aos_api.tenant_scope import TenantScope
    from a0v_qyh_current_product_event_first_chain import freeze, freeze_or_match
    scope = TenantScope("org-org", "dev-project")
    material = request.model_dump(mode="json", by_alias=True)
    intent = STATE / "register-intent.json"
    freeze_or_match(intent, material)
    service = plane.first_dispatch_registration_service
    try:
        receipt = service.read_successor_receipt(
            scope=scope, installation_id=BW_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact BW registration readback required")
    result = {"outcome": "CURRENT_BW_SUCCESSOR_REGISTERED", "request": material,
              "receipt": receipt, "replayed": not reconciled_absent}
    if not (STATE / "register-result.json").exists():
        freeze(STATE / "register-result.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preview", "register"])
    args = parser.parse_args()
    plane = setup()
    request = current_request()
    result = ({"outcome": "CURRENT_BW_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

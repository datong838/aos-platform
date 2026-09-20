#!/usr/bin/env python3
"""Register BX directly from the exact detached BW authority."""
from __future__ import annotations

import argparse
import json
import os

import a0v_av_successor_business as successor
import a0v_bx_replacement_recovery as bx_replacement


successor.STATE = bx_replacement.replacement.STATE / "registration-bx"
successor.AV_ID = "45db7b1e-6463-40f2-bf3c-c4e64ce3fd78"
successor.AV_GENERATION = "9beb5c99-aba7-4bec-9a10-4f98415aed2f"
successor.LOCK = "sha256:b4af00ba55283a22a08b1b045a3adc647854313856ebfd960bccff70f5a15152"
successor.CONFIG = {"configurationId": "a6ce6e53-6ef2-4e71-b5e1-87a37067ccd2", "revision": 1,
                    "hash": "sha256:968820ac265ee07dec85fd5c4808351233b1175bf6d2e0be4307825a69212e97"}
successor.AU_ID = "9b6e1277-a0a2-447d-9062-a98adfed3f22"
successor.AU_GENERATION = "62cf014b-9ce5-4512-8a34-b55a79e053c3"
successor.DETACH = "d3ca6ecb-5fea-4dda-8a30-3ac9f5ce047c"
successor.DETACH_HASH = "sha256:e1365bbc1f87d42997df4c04b5167d75895de232e69f81f9412e4ffaf9cebb5e"
successor.KEY = "a0v-qyh-clean-generation-bx-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 194
successor.PREDECESSOR_GROUP_REVISION = 221
successor.replacement_module = lambda: bx_replacement.replacement

BX_ID = successor.AV_ID
BX_GENERATION = successor.AV_GENERATION
AV_ID = BX_ID
AV_GENERATION = BX_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = bx_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = bx_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = bx_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_bx():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                bx_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_bx
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
            scope=scope, installation_id=BX_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact BX registration readback required")
    result = {"outcome": "CURRENT_BX_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_BX_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

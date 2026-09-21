#!/usr/bin/env python3
"""Register CX directly from the exact detached CW authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_cx_replacement_recovery as cx_replacement

successor.STATE = cx_replacement.replacement.STATE / "registration-cx"
successor.AV_ID = "2e374e12-7523-466d-aed7-bdabe8b69aff"
successor.AV_GENERATION = "222870ba-ad3c-4cf5-a6de-e1b3a52ab5bc"
successor.LOCK = "sha256:479419d261424399c29cac763588440b6ad4981b42bdf67b2a1615d16e715ccc"
successor.CONFIG = {"configurationId": "a548862b-ade7-4ff4-8796-54ebbfba6ee4", "revision": 1,
                    "hash": "sha256:955f42dcba8aa82a7c097fd661402f8f4c22ebd0f2b8abb753f609673459c1ef"}
successor.AU_ID = "0d5d5a7f-6e40-4725-b337-b79acc7d896a"
successor.AU_GENERATION = "a60036f1-5887-4157-ad32-616925b547bf"
successor.DETACH = "5aa372a9-1a82-41ff-b25e-00e898cda82a"
successor.DETACH_HASH = "sha256:2f121bf22c69efb2e4f37e1df1c17202c5c695e6a378459a92d07054108af78c"
successor.KEY = "a0v-qyh-clean-generation-cx-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 272
successor.PREDECESSOR_GROUP_REVISION = 299
successor.replacement_module = lambda: cx_replacement.replacement

CX_ID = successor.AV_ID
CX_GENERATION = successor.AV_GENERATION
AV_ID = CX_ID
AV_GENERATION = CX_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = cx_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = cx_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = cx_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_cx():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                cx_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_cx
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
            scope=scope, installation_id=CX_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact CX registration readback required")
    result = {"outcome": "CURRENT_CX_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_CX_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

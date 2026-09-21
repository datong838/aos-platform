#!/usr/bin/env python3
"""Register CG directly from the exact detached CF authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_cg_replacement_recovery as cg_replacement

successor.STATE = cg_replacement.replacement.STATE / "registration-cg"
successor.AV_ID = "8f42819c-0fc7-48cf-a5c4-9ba96894a6f5"
successor.AV_GENERATION = "3ed300fa-5fff-4949-9fb0-1926412e51ae"
successor.LOCK = "sha256:554edd86332cff3f2879d4167f2ae7b16f4836af736dd3ff2545b66a57a3438d"
successor.CONFIG = {"configurationId": "9ff22648-bbe3-4894-8ffd-fd85320e9a6b", "revision": 1,
                    "hash": "sha256:5ed349c44c4af8f61c4a0cf6dc0f6e328bed49a52ef3b37ffd947093fd3c740f"}
successor.AU_ID = "8cf0c597-cf81-4fa5-b1ff-f27e3537a94c"
successor.AU_GENERATION = "88996259-ad79-4aa6-962c-c29a24559db8"
successor.DETACH = "829cd86a-bf4e-4b62-a0e8-e3a89c34b9e0"
successor.DETACH_HASH = "sha256:0f2adfef50c42ed684a0ccdedf737a9a13a9e31b55d7b778b08f3f49e1bb2f6b"
successor.KEY = "a0v-qyh-clean-generation-cg-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 221
successor.PREDECESSOR_GROUP_REVISION = 248
successor.replacement_module = lambda: cg_replacement.replacement

CG_ID = successor.AV_ID
CG_GENERATION = successor.AV_GENERATION
AV_ID = CG_ID
AV_GENERATION = CG_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = cg_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = cg_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = cg_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment
        def configure_cg():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                cg_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")
        launcher.configure_environment = configure_cg
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
            scope=scope, installation_id=CG_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact CG registration readback required")
    result = {"outcome": "CURRENT_CG_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_CG_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

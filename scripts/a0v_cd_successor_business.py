#!/usr/bin/env python3
"""Register CD directly from the exact detached CC authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_cd_replacement_recovery as cd_replacement

successor.STATE = cd_replacement.replacement.STATE / "registration-cd"
successor.AV_ID = "01b41c17-fce2-4bcf-8d9e-a48d2d4bf743"
successor.AV_GENERATION = "22639b06-1211-424d-9f64-696822e0add4"
successor.LOCK = "sha256:3c38e9de616a063e451e53f23d0cf5ba08101a7ba0854904107fd5d3293ab65a"
successor.CONFIG = {"configurationId": "2ea2c035-df5e-4eb0-95aa-5283108c873d", "revision": 1,
                    "hash": "sha256:77289a41ae6647d649f429803d87c9f1ffbd3323c1ed89bd7cddf89a0db00c65"}
successor.AU_ID = "03942567-0f78-4530-b9dd-634bec59c780"
successor.AU_GENERATION = "c1ffee4f-c13b-4d1a-93d2-c3b35bd66ca2"
successor.DETACH = "af7f0b34-1279-4ca7-972b-ef0e31fd53b3"
successor.DETACH_HASH = "sha256:848870b0fd047ebf70beb0361ba99e9e4b72375138d66b2df8aeda9ee6c11ea3"
successor.KEY = "a0v-qyh-clean-generation-cd-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 212
successor.PREDECESSOR_GROUP_REVISION = 239
successor.replacement_module = lambda: cd_replacement.replacement

CD_ID = successor.AV_ID
CD_GENERATION = successor.AV_GENERATION
AV_ID = CD_ID
AV_GENERATION = CD_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = cd_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = cd_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = cd_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment
        def configure_cd():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                cd_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")
        launcher.configure_environment = configure_cd
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
            scope=scope, installation_id=CD_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact CD registration readback required")
    result = {"outcome": "CURRENT_CD_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_CD_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

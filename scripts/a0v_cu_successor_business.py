#!/usr/bin/env python3
"""Register CU directly from the exact detached CT authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_cu_replacement_recovery as cu_replacement

successor.STATE = cu_replacement.replacement.STATE / "registration-cu"
successor.AV_ID = "2c2d5506-1f80-4557-bf4b-00ead0258002"
successor.AV_GENERATION = "bcaa7ea0-62b1-4238-8615-28db45e3014e"
successor.LOCK = "sha256:3a1338060d903fc721f71e49b077ac130aa226f64a94e48d09d2ddab16f09200"
successor.CONFIG = {"configurationId": "12535ee1-99ae-449c-b3e8-41100a046f58", "revision": 1,
                    "hash": "sha256:6aa85c0d8cc9617f96c6e26a4b4b2d06459dbef30af70717274ea6b2b4168cad"}
successor.AU_ID = "b4847c85-b452-4c87-bf56-8a57bc9f8d25"
successor.AU_GENERATION = "0d234db2-8b76-4ec8-a14a-a8c6eec9bbc6"
successor.DETACH = "b1101390-ca5d-43bf-bc6a-c3bc0fc1d4f1"
successor.DETACH_HASH = "sha256:8809a0a0ff8a8e69291d737a28277a48ef6faea6b8520ae658c55b320ace7123"
successor.KEY = "a0v-qyh-clean-generation-cu-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 263
successor.PREDECESSOR_GROUP_REVISION = 290
successor.replacement_module = lambda: cu_replacement.replacement

CU_ID = successor.AV_ID
CU_GENERATION = successor.AV_GENERATION
AV_ID = CU_ID
AV_GENERATION = CU_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = cu_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = cu_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = cu_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_cu():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                cu_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_cu
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
            scope=scope, installation_id=CU_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact CU registration readback required")
    result = {"outcome": "CURRENT_CU_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_CU_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

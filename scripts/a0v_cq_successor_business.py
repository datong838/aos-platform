#!/usr/bin/env python3
"""Register CQ directly from the exact detached CP authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_cq_replacement_recovery as cq_replacement

successor.STATE = cq_replacement.replacement.STATE / "registration-cq"
successor.AV_ID = "fff0b0d3-bf8f-44b0-b1b7-6a2972daeb80"
successor.AV_GENERATION = "ae8a1005-99fb-48c5-9dfe-8f76590bc0c8"
successor.LOCK = "sha256:6b3debbfebb5b16297f35e2271944a8a9775b2c178922d31525655088f919b50"
successor.CONFIG = {"configurationId": "85103076-e401-4624-8141-4dc8374db731", "revision": 1,
                    "hash": "sha256:f63e3f688081dac051643213f06ab62d0193c60f8e14859f2a510897c891511c"}
successor.AU_ID = "1d8b71c5-1cde-4d16-b16f-835f92bf8663"
successor.AU_GENERATION = "9b0201fc-9822-4527-b63c-23cbd416057d"
successor.DETACH = "4603f48f-2d3a-4581-b837-b85658a2cf50"
successor.DETACH_HASH = "sha256:05a9ec8c3b477d23c0b329dded09c2d4ad08d686a2997fc36bb4bab46db95205"
successor.KEY = "a0v-qyh-clean-generation-cq-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 251
successor.PREDECESSOR_GROUP_REVISION = 278
successor.replacement_module = lambda: cq_replacement.replacement

CQ_ID = successor.AV_ID
CQ_GENERATION = successor.AV_GENERATION
AV_ID = CQ_ID
AV_GENERATION = CQ_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = cq_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = cq_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = cq_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_cq():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                cq_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_cq
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
            scope=scope, installation_id=CQ_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact CQ registration readback required")
    result = {"outcome": "CURRENT_CQ_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_CQ_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

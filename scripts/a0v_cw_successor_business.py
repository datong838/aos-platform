#!/usr/bin/env python3
"""Register CW directly from the exact detached CV authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_cw_replacement_recovery as cw_replacement

successor.STATE = cw_replacement.replacement.STATE / "registration-cw"
successor.AV_ID = "0d5d5a7f-6e40-4725-b337-b79acc7d896a"
successor.AV_GENERATION = "a60036f1-5887-4157-ad32-616925b547bf"
successor.LOCK = "sha256:ed07dc19c26651fd6c845702f96f3a881642361f29d2f6495052a230d1fa0162"
successor.CONFIG = {"configurationId": "3c8f431a-36fc-429c-aa4e-36f5a57a19b6", "revision": 1,
                    "hash": "sha256:5ba80fe04373371fb8d46773eebf265fb9f325a5e6b91fbf5f458f76bda9653a"}
successor.AU_ID = "f94149ca-a01e-4a20-836f-3f5132e0dbb7"
successor.AU_GENERATION = "82aec2b8-072d-4f2e-9624-f9539c8890a6"
successor.DETACH = "9add3bab-81be-417d-ab80-18f254ecf43f"
successor.DETACH_HASH = "sha256:a8bc901472293b85f1b6085e97ea673dbe3ea79216668d6b6c15ffb6a0fb9bea"
successor.KEY = "a0v-qyh-clean-generation-cw-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 269
successor.PREDECESSOR_GROUP_REVISION = 296
successor.replacement_module = lambda: cw_replacement.replacement

CW_ID = successor.AV_ID
CW_GENERATION = successor.AV_GENERATION
AV_ID = CW_ID
AV_GENERATION = CW_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = cw_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = cw_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = cw_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_cw():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                cw_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_cw
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
            scope=scope, installation_id=CW_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact CW registration readback required")
    result = {"outcome": "CURRENT_CW_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_CW_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

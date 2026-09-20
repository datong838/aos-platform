#!/usr/bin/env python3
"""Register BO directly from the exact detached BN authority."""
from __future__ import annotations

import argparse
import json
import os

import a0v_av_successor_business as successor
import a0v_bo_replacement_recovery as bo_replacement


successor.STATE = bo_replacement.replacement.STATE / "registration-bo"
successor.AV_ID = "307399a0-21bb-4d55-95b2-8b0fee238913"
successor.AV_GENERATION = "030bf59c-c998-4ee6-aedb-11d8d7d5831a"
successor.LOCK = "sha256:0e6dc143f25c8dc043b30b324719cce42c37dcb7bde08b51b0add161a70c860f"
successor.CONFIG = {"configurationId": "b7ed1c14-9cd1-4c78-95ea-c46ac80742d8", "revision": 1,
                    "hash": "sha256:3bee220829bb407782f5363541fff57731434d29d06c02236ceb8565f04260b3"}
successor.AU_ID = "d89bca67-4472-4b43-b0bd-ae8a2e0459f5"
successor.AU_GENERATION = "a43b3e64-7bb4-454c-822e-58bc13acbcaa"
successor.DETACH = "f581970a-fcff-403b-ad64-57c26e38831e"
successor.DETACH_HASH = "sha256:ec476774123dea036e212e6164b471510a4a536c3cf2ff137149d0437dc038d4"
successor.KEY = "a0v-qyh-clean-generation-bo-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 167
successor.PREDECESSOR_GROUP_REVISION = 194
successor.replacement_module = lambda: bo_replacement.replacement

BO_ID = successor.AV_ID
BO_GENERATION = successor.AV_GENERATION
AV_ID = BO_ID
AV_GENERATION = BO_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = bo_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = bo_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = bo_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_bo():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                bo_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")
        launcher.configure_environment = configure_bo
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
            scope=scope, installation_id=BO_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact BO registration readback required")
    result = {"outcome": "CURRENT_BO_SUCCESSOR_REGISTERED", "request": material,
              "receipt": receipt, "replayed": not reconciled_absent}
    if not (STATE / "register-result.json").exists():
        freeze(STATE / "register-result.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preview", "register"])
    args = parser.parse_args()
    plane = setup(); request = current_request()
    result = ({"outcome": "CURRENT_BO_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()} if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

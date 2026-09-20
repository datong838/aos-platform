#!/usr/bin/env python3
"""Register CC directly from the exact detached CB authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_cc_replacement_recovery as cc_replacement

successor.STATE = cc_replacement.replacement.STATE / "registration-cc"
successor.AV_ID = "03942567-0f78-4530-b9dd-634bec59c780"
successor.AV_GENERATION = "c1ffee4f-c13b-4d1a-93d2-c3b35bd66ca2"
successor.LOCK = "sha256:e90cdcbf95f12f2edcc711c51e55c67ad938364d894c40f0cf33d7f41313010b"
successor.CONFIG = {"configurationId": "c6ca556d-6fc3-4eb1-9956-b66b4901caf3", "revision": 1,
                    "hash": "sha256:773b1775a075582b47f464a9367d3c0b17b732e0b28f340e5631cd7d8f522bf5"}
successor.AU_ID = "3d6df614-5a05-4c6f-823e-688d81e84096"
successor.AU_GENERATION = "0cceac8c-c831-4b3f-92c3-fc35240c5414"
successor.DETACH = "087eed56-f46c-4a9b-bc57-ba24e2e78d04"
successor.DETACH_HASH = "sha256:ab3661056826d5a9998c8ba55d278317429fcb9286b7efa65fca467c2615be49"
successor.KEY = "a0v-qyh-clean-generation-cc-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 209
successor.PREDECESSOR_GROUP_REVISION = 236
successor.replacement_module = lambda: cc_replacement.replacement

CC_ID = successor.AV_ID
CC_GENERATION = successor.AV_GENERATION
AV_ID = CC_ID
AV_GENERATION = CC_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = cc_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = cc_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = cc_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment
        def configure_cc():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                cc_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")
        launcher.configure_environment = configure_cc
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
            scope=scope, installation_id=CC_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact CC registration readback required")
    result = {"outcome": "CURRENT_CC_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_CC_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

#!/usr/bin/env python3
"""Register BU directly from the exact detached BT authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_bu_replacement_recovery as bu_replacement

successor.STATE = bu_replacement.replacement.STATE / "registration-bu"
successor.AV_ID = "d1dcf5c2-f6ff-48b2-b6f1-fb05d17b7895"
successor.AV_GENERATION = "cb8ace71-ba8d-4e08-816b-8d6bbc0f0281"
successor.LOCK = "sha256:470af8d75bc784496260df85be7953537f2d2ead135167dc2d14f16e9bc1d2ed"
successor.CONFIG = {"configurationId": "15ceb457-eb93-492e-bc63-54438d198b44", "revision": 1,
                    "hash": "sha256:7f5d97cf81ff96988eabae4161448ef8bfe830b6c91a145dd2e5d5e33e642a22"}
successor.AU_ID = "b05b7f06-67a0-4ea1-bc7c-1ba2108653d5"
successor.AU_GENERATION = "2c2d4cd5-d9bd-45b4-86d9-72a979eb0a58"
successor.DETACH = "3c4c44d3-7f5f-4829-951a-5ba5c4c37aaa"
successor.DETACH_HASH = "sha256:49271deaba3745fe1f75f7e041b058f285f6706364cda4d8afddb0315b9c5528"
successor.KEY = "a0v-qyh-clean-generation-bu-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 185
successor.PREDECESSOR_GROUP_REVISION = 212
successor.replacement_module = lambda: bu_replacement.replacement

BU_ID = successor.AV_ID
BU_GENERATION = successor.AV_GENERATION
AV_ID = BU_ID
AV_GENERATION = BU_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = bu_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = bu_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = bu_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment
        def configure_bu():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                bu_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")
        launcher.configure_environment = configure_bu
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
            scope=scope, installation_id=BU_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact BU registration readback required")
    result = {"outcome": "CURRENT_BU_SUCCESSOR_REGISTERED", "request": material,
              "receipt": receipt, "replayed": not reconciled_absent}
    if not (STATE / "register-result.json").exists():
        freeze(STATE / "register-result.json", result)
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preview", "register"])
    args = parser.parse_args()
    plane = setup(); request = current_request()
    result = ({"outcome": "CURRENT_BU_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()} if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

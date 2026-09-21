#!/usr/bin/env python3
"""Register CK directly from the exact detached CJ authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_ck_replacement_recovery as ck_replacement

successor.STATE = ck_replacement.replacement.STATE / "registration-ck"
successor.AV_ID = "c1cb44ba-68ae-4d32-9974-5f031554fed2"
successor.AV_GENERATION = "1edb1688-e2b6-42f0-b513-849ae372859e"
successor.LOCK = "sha256:e7b527f80ede65ef8aeade78c0ea29a0199e6986f557e135c547521c4f637e4c"
successor.CONFIG = {"configurationId": "a5f8b32a-d92b-43a0-9afc-3e43d971e3f7", "revision": 1,
                    "hash": "sha256:b01c9641f33da1593ac2e1c2fc031b7a2cee89db5e1ae0c79e1bd8fa069a5196"}
successor.AU_ID = "184e0d1d-128a-462c-b677-d19bc5bf0891"
successor.AU_GENERATION = "f45f46a9-56ae-49b5-966d-083cdf19282b"
successor.DETACH = "54b8272c-dae1-4dca-833e-90a40bc77fba"
successor.DETACH_HASH = "sha256:9d8812adc4d156ee37149d5791920669c5684915f0399be6030cb358eb14e09d"
successor.KEY = "a0v-qyh-clean-generation-ck-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 233
successor.PREDECESSOR_GROUP_REVISION = 260
successor.replacement_module = lambda: ck_replacement.replacement

CK_ID = successor.AV_ID
CK_GENERATION = successor.AV_GENERATION
AV_ID = CK_ID
AV_GENERATION = CK_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = ck_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = ck_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = ck_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_ck():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                ck_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_ck
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
            scope=scope, installation_id=CK_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact CK registration readback required")
    result = {"outcome": "CURRENT_CK_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_CK_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

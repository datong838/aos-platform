#!/usr/bin/env python3
"""Register CP directly from the exact detached CO authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_cp_replacement_recovery as cp_replacement

successor.STATE = cp_replacement.replacement.STATE / "registration-cp"
successor.AV_ID = "1d8b71c5-1cde-4d16-b16f-835f92bf8663"
successor.AV_GENERATION = "9b0201fc-9822-4527-b63c-23cbd416057d"
successor.LOCK = "sha256:9eb345e2ed64ed8ea82b997218fc6a029a05c342c3e3fba58d85e55b6acf857e"
successor.CONFIG = {"configurationId": "d9e814b2-8a21-4db6-997a-0a3a8139dfef", "revision": 1,
                    "hash": "sha256:76f9707c8fb3edc71c26e3aa2ac6029bd5467101d293114b7abc2e11a232a8a8"}
successor.AU_ID = "648b267b-bb8f-4582-ab29-288279f534c7"
successor.AU_GENERATION = "db428c1b-2fe4-4869-8a69-ddffaa909ba7"
successor.DETACH = "d392b12f-9523-487e-aa9c-f473450e95cf"
successor.DETACH_HASH = "sha256:cccb32032a1403cfd5e5da25875f026330e2f95f743c6d78ba669f9ab576db96"
successor.KEY = "a0v-qyh-clean-generation-cp-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 248
successor.PREDECESSOR_GROUP_REVISION = 275
successor.replacement_module = lambda: cp_replacement.replacement

CP_ID = successor.AV_ID
CP_GENERATION = successor.AV_GENERATION
AV_ID = CP_ID
AV_GENERATION = CP_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = cp_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = cp_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = cp_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_cp():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                cp_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_cp
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
            scope=scope, installation_id=CP_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact CP registration readback required")
    result = {"outcome": "CURRENT_CP_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_CP_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

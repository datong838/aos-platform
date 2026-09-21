#!/usr/bin/env python3
"""Register CL directly from the exact detached CK authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_cl_replacement_recovery as cl_replacement

successor.STATE = cl_replacement.replacement.STATE / "registration-cl"
successor.AV_ID = "64e49f66-b0ef-4676-91c1-eb05f6d1d0b1"
successor.AV_GENERATION = "a583218d-f65b-4697-9e60-7281a0bff66e"
successor.LOCK = "sha256:9e4ab375110d6d458b98012872bc35a39545afc7e6d547ed48c57667f4838a8e"
successor.CONFIG = {"configurationId": "49fb289d-e60a-4f88-841e-dd866c901241", "revision": 1,
                    "hash": "sha256:633751d9a47c3829ae084e0ccf45908ef6acdef55bbf042a5754b73a1c2cdf4b"}
successor.AU_ID = "c1cb44ba-68ae-4d32-9974-5f031554fed2"
successor.AU_GENERATION = "1edb1688-e2b6-42f0-b513-849ae372859e"
successor.DETACH = "8ed70360-4e39-4a96-992f-d70f3222b541"
successor.DETACH_HASH = "sha256:812e9450e64a730d13b34db809903cbd61d3c537c4bc4fb3ba06eb09aaa15144"
successor.KEY = "a0v-qyh-clean-generation-cl-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 236
successor.PREDECESSOR_GROUP_REVISION = 263
successor.replacement_module = lambda: cl_replacement.replacement

CL_ID = successor.AV_ID
CL_GENERATION = successor.AV_GENERATION
AV_ID = CL_ID
AV_GENERATION = CL_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = cl_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = cl_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = cl_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_cl():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                cl_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_cl
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
            scope=scope, installation_id=CL_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact CL registration readback required")
    result = {"outcome": "CURRENT_CL_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_CL_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

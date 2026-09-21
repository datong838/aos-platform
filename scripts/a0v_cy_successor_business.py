#!/usr/bin/env python3
"""Register CY directly from the exact detached CX authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_cy_replacement_recovery as cy_replacement

successor.STATE = cy_replacement.replacement.STATE / "registration-cy"
successor.AV_ID = "917cd341-96a5-4428-9508-03c716c587ad"
successor.AV_GENERATION = "a2fdbdb1-430c-417b-969d-6bd30874d38c"
successor.LOCK = "sha256:8402d118a9ce1b12bbc4900144bc323634bd17e9a8b8af2e8de38cb9db637444"
successor.CONFIG = {"configurationId": "fee315dd-3e0e-4711-a50e-035b221689b0", "revision": 1,
                    "hash": "sha256:31c85642e697f29a41f2c101f83c1d0d0d320ec0d0be1bb1fa488889429d6e67"}
successor.AU_ID = "2e374e12-7523-466d-aed7-bdabe8b69aff"
successor.AU_GENERATION = "222870ba-ad3c-4cf5-a6de-e1b3a52ab5bc"
successor.DETACH = "7753b075-1795-4435-a49c-1fb9f609f8f9"
successor.DETACH_HASH = "sha256:21a1c832c8b2b6c462db82efda362a311fb1980402bea9da441156d8fdca5c0c"
successor.KEY = "a0v-qyh-clean-generation-cy-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 275
successor.PREDECESSOR_GROUP_REVISION = 302
successor.replacement_module = lambda: cy_replacement.replacement

CY_ID = successor.AV_ID
CY_GENERATION = successor.AV_GENERATION
AV_ID = CY_ID
AV_GENERATION = CY_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = cy_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = cy_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = cy_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_cy():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                cy_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_cy
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
            scope=scope, installation_id=CY_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact CY registration readback required")
    result = {"outcome": "CURRENT_CY_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_CY_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

#!/usr/bin/env python3
"""Register CZ directly from the exact detached CY authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_cz_replacement_recovery as cz_replacement

successor.STATE = cz_replacement.replacement.STATE / "registration-cz"
successor.AV_ID = "162e4c29-a24e-4c6b-8da7-9582d090d708"
successor.AV_GENERATION = "d1b0f7eb-9677-4d52-a656-a4ae28942976"
successor.LOCK = "sha256:b7045d4fb19c9f0482ac08a12cae8276c4878b3cb2290bd3f4ade0b5b7f885e6"
successor.CONFIG = {"configurationId": "e6c3bb08-906b-4f88-a5ae-6ee372a5afbb", "revision": 1,
                    "hash": "sha256:56f4cb520a135b69bad565b20b17648b17f0d5e1e727150be0a0c2066b8ca03e"}
successor.AU_ID = "917cd341-96a5-4428-9508-03c716c587ad"
successor.AU_GENERATION = "a2fdbdb1-430c-417b-969d-6bd30874d38c"
successor.DETACH = "90718b50-d3c8-4712-91c7-41b6ab0358bf"
successor.DETACH_HASH = "sha256:932ac829528ff8fa7da0d05239f70eee127df1f7e34e7da4a9d6b44d20899b03"
successor.KEY = "a0v-qyh-clean-generation-cz-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 278
successor.PREDECESSOR_GROUP_REVISION = 305
successor.replacement_module = lambda: cz_replacement.replacement

CZ_ID = successor.AV_ID
CZ_GENERATION = successor.AV_GENERATION
AV_ID = CZ_ID
AV_GENERATION = CZ_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = cz_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = cz_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = cz_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_cz():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                cz_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_cz
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
            scope=scope, installation_id=CZ_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact CZ registration readback required")
    result = {"outcome": "CURRENT_CZ_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_CZ_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

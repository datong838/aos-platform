#!/usr/bin/env python3
"""Register CM directly from the exact detached CL authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_cm_replacement_recovery as cm_replacement

successor.STATE = cm_replacement.replacement.STATE / "registration-cm"
successor.AV_ID = "b52c8e1c-a343-4ef4-b106-38d859ba9677"
successor.AV_GENERATION = "d3ec88cc-a05a-4895-bc27-c983a367a9a8"
successor.LOCK = "sha256:50f9a34602014a44de489eb978c6684706aeff1435733684b2262133fce553ab"
successor.CONFIG = {"configurationId": "3706e919-0153-4aca-aa4c-69ab18960d3c", "revision": 1,
                    "hash": "sha256:12397b16ac8fb7d57a098e8f6203b8533c59d78d3bf11bc0b5d6371282394c6d"}
successor.AU_ID = "64e49f66-b0ef-4676-91c1-eb05f6d1d0b1"
successor.AU_GENERATION = "a583218d-f65b-4697-9e60-7281a0bff66e"
successor.DETACH = "03e11531-9fb5-4453-80dd-2d2d07051bec"
successor.DETACH_HASH = "sha256:b93907af1a3ace36e10d83da4e199da17c80aaa0b9cdbc557b88a54fed721992"
successor.KEY = "a0v-qyh-clean-generation-cm-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 239
successor.PREDECESSOR_GROUP_REVISION = 266
successor.replacement_module = lambda: cm_replacement.replacement

CM_ID = successor.AV_ID
CM_GENERATION = successor.AV_GENERATION
AV_ID = CM_ID
AV_GENERATION = CM_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = cm_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = cm_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = cm_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_cm():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                cm_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_cm
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
            scope=scope, installation_id=CM_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact CM registration readback required")
    result = {"outcome": "CURRENT_CM_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_CM_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

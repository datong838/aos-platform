#!/usr/bin/env python3
"""Register DI directly from the exact detached DH authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_di_replacement_recovery as di_replacement


successor.STATE = di_replacement.replacement.STATE / "registration-di"
successor.AV_ID = "c8298a5d-9d94-4c37-81c9-508e2f0faf60"
successor.AV_GENERATION = "56950fc1-4007-497a-8a09-df133a1950c1"
successor.LOCK = "sha256:306ffd56004521bf793df38eb4887287afbec98279c169e64aaae469a5dbfffc"
successor.CONFIG = {"configurationId": "6d8cc828-307e-407d-b3ed-37a3ed524114", "revision": 1,
                    "hash": "sha256:0b6534e9fd9f8e4f900cd3208d446340735a95dbaafc21d5285498bea47a2861"}
successor.AU_ID = "10d583ad-96ee-4b1a-bb18-92e428abe16e"
successor.AU_GENERATION = "107a24f5-691d-4f2a-9b46-4e7b21938146"
successor.DETACH = "6a8a6daa-1c32-45af-89f4-3bb2cf7ac80c"
successor.DETACH_HASH = "sha256:505640a22de3ee4b9cec5c9de036c7d3ff05e55bb2472f9d1bdadc5150220ea3"
successor.KEY = "a0v-qyh-clean-generation-di-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 305
successor.PREDECESSOR_GROUP_REVISION = 332
successor.replacement_module = lambda: di_replacement.replacement

DI_ID = successor.AV_ID
DI_GENERATION = successor.AV_GENERATION
AV_ID = DI_ID
AV_GENERATION = DI_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = di_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = di_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = di_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_di():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                di_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_di
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
            scope=scope, installation_id=DI_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact DI registration readback required")
    result = {"outcome": "CURRENT_DI_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_DI_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

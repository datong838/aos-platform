#!/usr/bin/env python3
"""Register DG directly from the exact detached DF authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_dg_replacement_recovery as dg_replacement


successor.STATE = dg_replacement.replacement.STATE / "registration-dg"
successor.AV_ID = "d551d104-f240-4b27-b738-1ef47129b5a4"
successor.AV_GENERATION = "6c1780ab-746b-4303-a9ad-dc30039af8a4"
successor.LOCK = "sha256:63f93357f433f7b9c85c0316eb746ea66b61642b00cde388fabde339a33312a2"
successor.CONFIG = {"configurationId": "6611514e-e940-4df3-a7bf-bff441a5bc37", "revision": 1,
                    "hash": "sha256:c5c763bb916f9893de57dafea8c44b96e5996157c87e0fbea9079c9f2078a757"}
successor.AU_ID = "a0639f78-af04-4249-97f6-d8507de45f44"
successor.AU_GENERATION = "ec18c8c6-2694-44c1-a9c9-ea79ea606e45"
successor.DETACH = "6c1dbb1e-6aec-4276-97fd-5bf7ee90ae03"
successor.DETACH_HASH = "sha256:a7cecfce6cd17074fcff0ce9feec405d5d95eaf1a117466b2a4b5db7f3f51330"
successor.KEY = "a0v-qyh-clean-generation-dg-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 299
successor.PREDECESSOR_GROUP_REVISION = 326
successor.replacement_module = lambda: dg_replacement.replacement

DG_ID = successor.AV_ID
DG_GENERATION = successor.AV_GENERATION
AV_ID = DG_ID
AV_GENERATION = DG_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = dg_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = dg_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = dg_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_dg():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                dg_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_dg
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
            scope=scope, installation_id=DG_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact DG registration readback required")
    result = {"outcome": "CURRENT_DG_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_DG_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

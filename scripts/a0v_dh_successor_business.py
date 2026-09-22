#!/usr/bin/env python3
"""Register DH directly from the exact detached DG authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_dh_replacement_recovery as dh_replacement


successor.STATE = dh_replacement.replacement.STATE / "registration-dh"
successor.AV_ID = "10d583ad-96ee-4b1a-bb18-92e428abe16e"
successor.AV_GENERATION = "107a24f5-691d-4f2a-9b46-4e7b21938146"
successor.LOCK = "sha256:aad5193620d1517a9b3be224440004eb040ad4b439d057ea0291ff0724d5d334"
successor.CONFIG = {"configurationId": "b1a8b55d-e393-4dbb-b416-7dfb2dbe9874", "revision": 1,
                    "hash": "sha256:91024b4c4c600019589f868bcc00d904818a0ffce73a34924e678ee7ea8e76f0"}
successor.AU_ID = "d551d104-f240-4b27-b738-1ef47129b5a4"
successor.AU_GENERATION = "6c1780ab-746b-4303-a9ad-dc30039af8a4"
successor.DETACH = "6d21f82c-7521-4c36-89c0-06f360339b02"
successor.DETACH_HASH = "sha256:7bd17d373e1281fbb5768e5b99b839b617d30c89a2e3e088afcb285818129c22"
successor.KEY = "a0v-qyh-clean-generation-dh-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 302
successor.PREDECESSOR_GROUP_REVISION = 329
successor.replacement_module = lambda: dh_replacement.replacement

DH_ID = successor.AV_ID
DH_GENERATION = successor.AV_GENERATION
AV_ID = DH_ID
AV_GENERATION = DH_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = dh_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = dh_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = dh_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_dh():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                dh_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_dh
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
            scope=scope, installation_id=DH_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact DH registration readback required")
    result = {"outcome": "CURRENT_DH_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_DH_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

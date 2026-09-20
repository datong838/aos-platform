#!/usr/bin/env python3
"""Register BY directly from the exact detached BX authority."""
from __future__ import annotations

import argparse
import json
import os

import a0v_av_successor_business as successor
import a0v_by_replacement_recovery as by_replacement


successor.STATE = by_replacement.replacement.STATE / "registration-by"
successor.AV_ID = "ed64db1a-45eb-442e-8f1b-49ed899731dc"
successor.AV_GENERATION = "01f99334-0515-4c73-b442-a293709b3cc2"
successor.LOCK = "sha256:77165c48df63d332cebf02dfa35f59711d7d1af5dc5f396db86c23400f3653cc"
successor.CONFIG = {"configurationId": "deb4dc29-2564-4ad8-b1bc-9178ef2f1671", "revision": 1,
                    "hash": "sha256:204b447e8fa0c68cb26e02d1e8697faebaeede47fe8028b67cb9190640aaee18"}
successor.AU_ID = "45db7b1e-6463-40f2-bf3c-c4e64ce3fd78"
successor.AU_GENERATION = "9beb5c99-aba7-4bec-9a10-4f98415aed2f"
successor.DETACH = "608d36a3-198b-46e2-bc5b-d653e44d44c8"
successor.DETACH_HASH = "sha256:1862820a36540eb75b301673e8c5e4553cd1c2f05facf602a35dda4c20754e9c"
successor.KEY = "a0v-qyh-clean-generation-by-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 197
successor.PREDECESSOR_GROUP_REVISION = 224
successor.replacement_module = lambda: by_replacement.replacement

BY_ID = successor.AV_ID
BY_GENERATION = successor.AV_GENERATION
AV_ID = BY_ID
AV_GENERATION = BY_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = by_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = by_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = by_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_by():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                by_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_by
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
            scope=scope, installation_id=BY_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact BY registration readback required")
    result = {"outcome": "CURRENT_BY_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_BY_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

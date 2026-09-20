#!/usr/bin/env python3
"""Register BQ directly from the exact detached BP authority."""
from __future__ import annotations

import argparse
import json
import os

import a0v_av_successor_business as successor
import a0v_bq_replacement_recovery as bq_replacement


successor.STATE = bq_replacement.replacement.STATE / "registration-bq"
successor.AV_ID = "4faaf3b7-2d10-4961-99db-5bf52b7b8a63"
successor.AV_GENERATION = "b53ce5ac-169c-4d69-9780-58beb8ad736c"
successor.LOCK = "sha256:b072f76743abd5ae543c7cf37ad0bfb3e569a40b188998a03d2e94a5e7ae713f"
successor.CONFIG = {"configurationId": "03c66bc4-7c73-45c0-8fec-84e1d9fb1bab", "revision": 1,
                    "hash": "sha256:741b4688b34c58917d60555ffd58511a48611248da31a608c6e21f8b39bb5a15"}
successor.AU_ID = "17ba9792-9f24-42e4-9557-4d84547c7d97"
successor.AU_GENERATION = "4f1bddfa-74a0-4fcb-b25e-f363139eed83"
successor.DETACH = "ae6695f9-42bf-41a3-a09d-0f3c092e4793"
successor.DETACH_HASH = "sha256:f71f9eb5fdb860bd7cc068109686699c2db641a702d813fb9ec7b204f599b7c0"
successor.KEY = "a0v-qyh-clean-generation-bq-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 173
successor.PREDECESSOR_GROUP_REVISION = 200
successor.replacement_module = lambda: bq_replacement.replacement

BQ_ID = successor.AV_ID
BQ_GENERATION = successor.AV_GENERATION
AV_ID = BQ_ID
AV_GENERATION = BQ_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = bq_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = bq_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = bq_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_bq():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                bq_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")
        launcher.configure_environment = configure_bq
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
            scope=scope, installation_id=BQ_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact BQ registration readback required")
    result = {"outcome": "CURRENT_BQ_SUCCESSOR_REGISTERED", "request": material,
              "receipt": receipt, "replayed": not reconciled_absent}
    if not (STATE / "register-result.json").exists():
        freeze(STATE / "register-result.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preview", "register"])
    args = parser.parse_args()
    plane = setup(); request = current_request()
    result = ({"outcome": "CURRENT_BQ_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()} if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

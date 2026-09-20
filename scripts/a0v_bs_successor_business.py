#!/usr/bin/env python3
"""Register BS directly from the exact detached BR authority."""
from __future__ import annotations

import argparse
import json
import os

import a0v_av_successor_business as successor
import a0v_bs_replacement_recovery as bs_replacement


successor.STATE = bs_replacement.replacement.STATE / "registration-bs"
successor.AV_ID = "c5a95204-c379-4763-b697-b4417349d204"
successor.AV_GENERATION = "6f8bcb56-5717-4d7a-9a9e-97c1982db053"
successor.LOCK = "sha256:0a3e5483351102d624ea389fafc865266c3ad642c70466068146705d4507c6ec"
successor.CONFIG = {"configurationId": "3ce0182e-57b1-4c14-ad48-54cc4de63dfa", "revision": 1,
                    "hash": "sha256:2c10d539e11a332e9ec27ce31c23d3e4b0b7a0b0b182e32c402c8d32e584e722"}
successor.AU_ID = "fddfa0b0-158c-4271-b1ea-dc4e1e36e293"
successor.AU_GENERATION = "981d7a2d-3bbe-4cc1-a8d9-c872be0147d3"
successor.DETACH = "f4ca1d45-b002-47d2-b56a-15f6b57f7b3b"
successor.DETACH_HASH = "sha256:2a476a8b1e9f22247726c75ef5dae82eb043b339a501e7ea13b776324c6b48bc"
successor.KEY = "a0v-qyh-clean-generation-bs-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 179
successor.PREDECESSOR_GROUP_REVISION = 206
successor.replacement_module = lambda: bs_replacement.replacement

BS_ID = successor.AV_ID
BS_GENERATION = successor.AV_GENERATION
AV_ID = BS_ID
AV_GENERATION = BS_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = bs_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = bs_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = bs_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_bs():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                bs_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")
        launcher.configure_environment = configure_bs
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
            scope=scope, installation_id=BS_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact BS registration readback required")
    result = {"outcome": "CURRENT_BS_SUCCESSOR_REGISTERED", "request": material,
              "receipt": receipt, "replayed": not reconciled_absent}
    if not (STATE / "register-result.json").exists():
        freeze(STATE / "register-result.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preview", "register"])
    args = parser.parse_args()
    plane = setup(); request = current_request()
    result = ({"outcome": "CURRENT_BS_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()} if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

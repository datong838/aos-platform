#!/usr/bin/env python3
"""Register BR directly from the exact detached BQ authority."""
from __future__ import annotations

import argparse
import json
import os

import a0v_av_successor_business as successor
import a0v_br_replacement_recovery as br_replacement


successor.STATE = br_replacement.replacement.STATE / "registration-br"
successor.AV_ID = "fddfa0b0-158c-4271-b1ea-dc4e1e36e293"
successor.AV_GENERATION = "981d7a2d-3bbe-4cc1-a8d9-c872be0147d3"
successor.LOCK = "sha256:8fdef3f38ad4a6967cd378dea37ff7e540b31046e424de6bbc8e3a49ff9ce414"
successor.CONFIG = {"configurationId": "6ece45b0-a500-4fce-b0b2-fa55ec03837f", "revision": 1,
                    "hash": "sha256:1c3b3e4e666d80897b1be67d34296f4bb35f3936ad51cde49c86129eb6487524"}
successor.AU_ID = "4faaf3b7-2d10-4961-99db-5bf52b7b8a63"
successor.AU_GENERATION = "b53ce5ac-169c-4d69-9780-58beb8ad736c"
successor.DETACH = "82c3e7a5-64ad-4d4d-9cd1-d7c2c2f8fa3b"
successor.DETACH_HASH = "sha256:ae12194af3b1991fe3ba7e148d67d90a47d7213d33cb707ad7956380bdf98e4f"
successor.KEY = "a0v-qyh-clean-generation-br-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 176
successor.PREDECESSOR_GROUP_REVISION = 203
successor.replacement_module = lambda: br_replacement.replacement

BR_ID = successor.AV_ID
BR_GENERATION = successor.AV_GENERATION
AV_ID = BR_ID
AV_GENERATION = BR_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = br_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = br_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = br_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_br():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                br_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")
        launcher.configure_environment = configure_br
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
            scope=scope, installation_id=BR_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact BR registration readback required")
    result = {"outcome": "CURRENT_BR_SUCCESSOR_REGISTERED", "request": material,
              "receipt": receipt, "replayed": not reconciled_absent}
    if not (STATE / "register-result.json").exists():
        freeze(STATE / "register-result.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preview", "register"])
    args = parser.parse_args()
    plane = setup(); request = current_request()
    result = ({"outcome": "CURRENT_BR_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()} if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

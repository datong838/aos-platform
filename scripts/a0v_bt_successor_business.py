#!/usr/bin/env python3
"""Register BT directly from the exact detached BS authority."""
from __future__ import annotations

import argparse
import json
import os

import a0v_av_successor_business as successor
import a0v_bt_replacement_recovery as bt_replacement


successor.STATE = bt_replacement.replacement.STATE / "registration-bt"
successor.AV_ID = "b05b7f06-67a0-4ea1-bc7c-1ba2108653d5"
successor.AV_GENERATION = "2c2d4cd5-d9bd-45b4-86d9-72a979eb0a58"
successor.LOCK = "sha256:053ba1e22ac7ddb9a0ff227643fe3bda76d37d8cc38e808df351954614edb974"
successor.CONFIG = {"configurationId": "f4894956-2030-41a7-8794-32fbd458682a", "revision": 1,
                    "hash": "sha256:1424de1b55ddc6105160570a813a81800acd3fbf11cdd83f55395730a8dba8cb"}
successor.AU_ID = "c5a95204-c379-4763-b697-b4417349d204"
successor.AU_GENERATION = "6f8bcb56-5717-4d7a-9a9e-97c1982db053"
successor.DETACH = "ddd1e074-b90d-411e-93a3-0595d6e86d8b"
successor.DETACH_HASH = "sha256:2995a8a4d8d2a74ddbde34a521de984af0afad13844303f6883befe48fe58242"
successor.KEY = "a0v-qyh-clean-generation-bt-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 182
successor.PREDECESSOR_GROUP_REVISION = 209
successor.replacement_module = lambda: bt_replacement.replacement

BT_ID = successor.AV_ID
BT_GENERATION = successor.AV_GENERATION
AV_ID = BT_ID
AV_GENERATION = BT_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = bt_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = bt_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = bt_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_bt():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                bt_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")
        launcher.configure_environment = configure_bt
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
            scope=scope, installation_id=BT_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact BT registration readback required")
    result = {"outcome": "CURRENT_BT_SUCCESSOR_REGISTERED", "request": material,
              "receipt": receipt, "replayed": not reconciled_absent}
    if not (STATE / "register-result.json").exists():
        freeze(STATE / "register-result.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preview", "register"])
    args = parser.parse_args()
    plane = setup(); request = current_request()
    result = ({"outcome": "CURRENT_BT_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()} if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

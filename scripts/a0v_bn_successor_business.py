#!/usr/bin/env python3
"""Register BN directly from the exact detached BL authority."""
from __future__ import annotations

import argparse
import json
import os

import a0v_av_successor_business as successor
import a0v_bn_replacement_recovery as bn_replacement


successor.STATE = bn_replacement.replacement.STATE / "registration-bn"
successor.AV_ID = "d89bca67-4472-4b43-b0bd-ae8a2e0459f5"
successor.AV_GENERATION = "a43b3e64-7bb4-454c-822e-58bc13acbcaa"
successor.LOCK = "sha256:d0f24b0d57a20c0c2606609794c386471484711d823f63c05752db160ea09d9b"
successor.CONFIG = {"configurationId": "ddfb0b72-f106-4136-8222-41cf04349724", "revision": 1,
                    "hash": "sha256:b36ad7ae5f4c6f3b05e3fcb971ca0b533ae1f6fdf36e5b959d9d49ae5b4de910"}
successor.AU_ID = "ac9b3ec8-68ad-4e05-9f30-b2f8f6a473bc"
successor.AU_GENERATION = "116d12fc-93bc-4071-a973-fdc6830ea8b1"
successor.DETACH = "3a50db9a-2dec-4543-b37a-701a8e12ee36"
successor.DETACH_HASH = "sha256:265c6dcf811b6df90e5402fc7f1bc53aad22d8f49d29ec7caffe90f779a40f15"
successor.KEY = "a0v-qyh-clean-generation-bn-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 8
successor.PREDECESSOR_EXECUTION_EPOCH = 4
successor.PREDECESSOR_ROUTE_REVISION = 164
successor.PREDECESSOR_GROUP_REVISION = 191
successor.replacement_module = lambda: bn_replacement.replacement

BN_ID = successor.AV_ID
BN_GENERATION = successor.AV_GENERATION
AV_ID = BN_ID
AV_GENERATION = BN_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = bn_replacement.CREDENTIALS
        launcher.BUNDLE_ROOT = bn_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = bn_replacement.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_bn():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                bn_replacement.BASE / "bn-registration-credentials/registration-main-identity.json"
            )

        launcher.configure_environment = configure_bn
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
            scope=scope, installation_id=BN_ID, idempotency_key=KEY, actor=ACTOR
        )
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact BN registration readback required")
    result = {"outcome": "CURRENT_BN_SUCCESSOR_REGISTERED", "request": material,
              "receipt": receipt, "replayed": not reconciled_absent,
              "priorAttemptReconciledAbsent": reconciled_absent}
    if not (STATE / "register-result.json").exists():
        freeze(STATE / "register-result.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preview", "register"])
    args = parser.parse_args()
    plane = setup(); request = current_request()
    result = ({"outcome": "CURRENT_BN_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()} if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

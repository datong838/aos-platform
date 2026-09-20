#!/usr/bin/env python3
"""Register BV directly from the exact detached BU authority."""
from __future__ import annotations

import argparse
import json
import os

import a0v_av_successor_business as successor
import a0v_bv_replacement_recovery as bv_replacement


successor.STATE = bv_replacement.replacement.STATE / "registration-bv"
successor.AV_ID = "2b1aa826-b595-40d4-aeb2-9a7ce9d33c36"
successor.AV_GENERATION = "e8a5b32b-9a29-41bf-9c7f-87c7cd96b359"
successor.LOCK = "sha256:5b994767e0abd7c6138b611e96dae1948ff1812dd02aeb23ad38b229280eb73f"
successor.CONFIG = {"configurationId": "b59d1502-501b-46ae-ba80-80466017cacd", "revision": 1,
                    "hash": "sha256:4525829c23f4afbd01adcaafef57648c80c8a4bbd984a6125af6a3e38a5ba3c6"}
successor.AU_ID = "d1dcf5c2-f6ff-48b2-b6f1-fb05d17b7895"
successor.AU_GENERATION = "cb8ace71-ba8d-4e08-816b-8d6bbc0f0281"
successor.DETACH = "b071b45a-1e66-4898-b79c-49f1fdcd69ea"
successor.DETACH_HASH = "sha256:1eba5bd30d384de6ab165e9a617c7963fda5216775506d0341adfd1b63488163"
successor.KEY = "a0v-qyh-clean-generation-bv-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 188
successor.PREDECESSOR_GROUP_REVISION = 215
successor.replacement_module = lambda: bv_replacement.replacement

BV_ID = successor.AV_ID
BV_GENERATION = successor.AV_GENERATION
AV_ID = BV_ID
AV_GENERATION = BV_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = bv_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = bv_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = bv_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_bv():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                bv_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_bv
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
            scope=scope, installation_id=BV_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact BV registration readback required")
    result = {"outcome": "CURRENT_BV_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_BV_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

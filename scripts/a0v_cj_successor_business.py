#!/usr/bin/env python3
"""Register CJ directly from the exact detached CI authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_cj_replacement_recovery as cj_replacement

successor.STATE = cj_replacement.replacement.STATE / "registration-cj"
successor.AV_ID = "184e0d1d-128a-462c-b677-d19bc5bf0891"
successor.AV_GENERATION = "f45f46a9-56ae-49b5-966d-083cdf19282b"
successor.LOCK = "sha256:f96d6d2a702e0b4847ae259233fc50976ca5763462eb975359b5344edf758537"
successor.CONFIG = {"configurationId": "9bcc61bc-2e5d-414c-a7ce-62a6b94a2639", "revision": 1,
                    "hash": "sha256:633c115825d577437d5b11c3e33d19644077bb9efbc0e2f627b862fc61ae3302"}
successor.AU_ID = "1b9f500d-48a0-4f2c-8284-3db26e5cd4e7"
successor.AU_GENERATION = "8de8994b-ad87-4039-a851-d944153bca08"
successor.DETACH = "700c9914-c3ed-4360-8769-5f8d09307352"
successor.DETACH_HASH = "sha256:5cc5d6e9cf6a284f6e9533438f225291042162573aee209ff9b9cbc20893c4dd"
successor.KEY = "a0v-qyh-clean-generation-cj-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 230
successor.PREDECESSOR_GROUP_REVISION = 257
successor.replacement_module = lambda: cj_replacement.replacement

CJ_ID = successor.AV_ID
CJ_GENERATION = successor.AV_GENERATION
AV_ID = CJ_ID
AV_GENERATION = CJ_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = cj_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = cj_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = cj_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_cj():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                cj_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_cj
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
            scope=scope, installation_id=CJ_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact CJ registration readback required")
    result = {"outcome": "CURRENT_CJ_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_CJ_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

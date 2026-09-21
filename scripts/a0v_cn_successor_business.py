#!/usr/bin/env python3
"""Register CN directly from the exact detached CM authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_cn_replacement_recovery as cn_replacement

successor.STATE = cn_replacement.replacement.STATE / "registration-cn"
successor.AV_ID = "1366f4dd-47d9-42c1-b26a-759c7bd556da"
successor.AV_GENERATION = "cd0601e0-2668-496d-9f93-561d2e69a170"
successor.LOCK = "sha256:18045e8ebd31484b42a6ae4cebb9eb81b5d56be02b3a5929405ad2957f0c96bb"
successor.CONFIG = {"configurationId": "6b8a4673-8eef-487d-9bc6-a139b3b311ed", "revision": 1,
                    "hash": "sha256:d371bf7e45252e48e9a4174d67eea55d0a43e7e7dad1b039ce500b3c0cbad4b8"}
successor.AU_ID = "b52c8e1c-a343-4ef4-b106-38d859ba9677"
successor.AU_GENERATION = "d3ec88cc-a05a-4895-bc27-c983a367a9a8"
successor.DETACH = "a118ae49-92de-477a-92f3-0d855c48a472"
successor.DETACH_HASH = "sha256:5074648fad39e4be7040cac99fc18cc0748a6d162e2700ea0d78aa19c80803af"
successor.KEY = "a0v-qyh-clean-generation-cn-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 242
successor.PREDECESSOR_GROUP_REVISION = 269
successor.replacement_module = lambda: cn_replacement.replacement

CN_ID = successor.AV_ID
CN_GENERATION = successor.AV_GENERATION
AV_ID = CN_ID
AV_GENERATION = CN_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = cn_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = cn_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = cn_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_cn():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                cn_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_cn
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
            scope=scope, installation_id=CN_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact CN registration readback required")
    result = {"outcome": "CURRENT_CN_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_CN_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

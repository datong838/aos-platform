#!/usr/bin/env python3
"""Register DB directly from the exact detached DA authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_db_replacement_recovery as db_replacement

successor.STATE = db_replacement.replacement.STATE / "registration-db"
successor.AV_ID = "aaaa1ac1-2c35-4c35-8e7b-3ed6cd47f9c8"
successor.AV_GENERATION = "c1ae6205-0743-483c-82e3-1d1c95b1ab31"
successor.LOCK = "sha256:f277f3d8cba10eb9beb19b18e21f37814a485e271f09ce36c6005dc3723c5484"
successor.CONFIG = {"configurationId": "f0de4ad9-9cef-4cf1-8dde-8d6e9b44e21e", "revision": 1,
                    "hash": "sha256:52299fe7eb23c22092a6fdf3414ea369e805636e8cc743cd1f119c6968621294"}
successor.AU_ID = "f4fcdf0b-a37b-419c-9de0-14b08cd7320d"
successor.AU_GENERATION = "dbcdd8cb-c6f4-47cc-91f9-1662f54044c0"
successor.DETACH = "4285f549-aa8f-4d98-b370-ed2cdf040381"
successor.DETACH_HASH = "sha256:bf47d2487469ca9eb6092a68dd5ad980ace527d58615490dac59f4f8292b5ab7"
successor.KEY = "a0v-qyh-clean-generation-db-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 284
successor.PREDECESSOR_GROUP_REVISION = 311
successor.replacement_module = lambda: db_replacement.replacement

DB_ID = successor.AV_ID
DB_GENERATION = successor.AV_GENERATION
AV_ID = DB_ID
AV_GENERATION = DB_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = db_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = db_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = db_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_db():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                db_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_db
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
            scope=scope, installation_id=DB_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact DB registration readback required")
    result = {"outcome": "CURRENT_DB_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_DB_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

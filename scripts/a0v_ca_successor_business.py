#!/usr/bin/env python3
"""Register CA directly from the exact detached BZ authority."""
from __future__ import annotations

import argparse
import json
import os

import a0v_av_successor_business as successor
import a0v_ca_replacement_recovery as ca_replacement


successor.STATE = ca_replacement.replacement.STATE / "registration-ca"
successor.AV_ID = "0d834ab1-fd2b-4dbc-b9a5-0f0dee712647"
successor.AV_GENERATION = "1f18a077-12c6-4242-982a-0c3fa1159540"
successor.LOCK = "sha256:00c2ccaa82e00eb0e23f4e7dcd2491b674cb37caaf5d0e1a027709f6c8f47d7a"
successor.CONFIG = {"configurationId": "1ce3f7b8-8d08-4e4d-8324-631e259d944b", "revision": 1,
                    "hash": "sha256:f124e09f3b77296e6fe8873df6880722629b496d40d585bd425dd42bb2f03e15"}
successor.AU_ID = "9b30837c-da4d-4cfd-b438-de40aa5e3d7a"
successor.AU_GENERATION = "6f1e6e77-24aa-4052-9102-88e4a432fe55"
successor.DETACH = "a5ab50b1-aa8a-4418-9ed9-59a454d9055d"
successor.DETACH_HASH = "sha256:3f234f4c5d965b0b824383ff20f980c2f4ed2555c0aab59aac037289b4bfd9eb"
successor.KEY = "a0v-qyh-clean-generation-ca-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 203
successor.PREDECESSOR_GROUP_REVISION = 230
successor.replacement_module = lambda: ca_replacement.replacement

CA_ID = successor.AV_ID
CA_GENERATION = successor.AV_GENERATION
AV_ID = CA_ID
AV_GENERATION = CA_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = ca_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = ca_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = ca_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_ca():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                ca_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_ca
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
            scope=scope, installation_id=CA_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact CA registration readback required")
    result = {"outcome": "CURRENT_CA_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_CA_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

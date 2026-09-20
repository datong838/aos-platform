#!/usr/bin/env python3
"""Register BZ directly from the exact detached BY authority."""
from __future__ import annotations

import argparse
import json
import os

import a0v_av_successor_business as successor
import a0v_bz_replacement_recovery as bz_replacement


successor.STATE = bz_replacement.replacement.STATE / "registration-bz"
successor.AV_ID = "9b30837c-da4d-4cfd-b438-de40aa5e3d7a"
successor.AV_GENERATION = "6f1e6e77-24aa-4052-9102-88e4a432fe55"
successor.LOCK = "sha256:710bd45e92ed91c1e9a634e12eb4bdd8d9a4c8cee32191537dcd62c929e277af"
successor.CONFIG = {"configurationId": "cba5179d-e82a-4c58-87b4-3aecc33579ed", "revision": 1,
                    "hash": "sha256:c7c9f75c2737a4dfc30cfec6ac7b87275d5e42b107227b03fcdbc99f61f3772c"}
successor.AU_ID = "ed64db1a-45eb-442e-8f1b-49ed899731dc"
successor.AU_GENERATION = "01f99334-0515-4c73-b442-a293709b3cc2"
successor.DETACH = "476431d3-9cb4-4e5f-bd4b-02ac2c9fd978"
successor.DETACH_HASH = "sha256:d65a5f35ed1e32e2db5e71e93e2a201eff195fe8e0ce6a859cceee468da3dbcb"
successor.KEY = "a0v-qyh-clean-generation-bz-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 200
successor.PREDECESSOR_GROUP_REVISION = 227
successor.replacement_module = lambda: bz_replacement.replacement

BZ_ID = successor.AV_ID
BZ_GENERATION = successor.AV_GENERATION
AV_ID = BZ_ID
AV_GENERATION = BZ_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = bz_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = bz_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = bz_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_bz():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                bz_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_bz
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
            scope=scope, installation_id=BZ_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact BZ registration readback required")
    result = {"outcome": "CURRENT_BZ_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_BZ_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

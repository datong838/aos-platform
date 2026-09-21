#!/usr/bin/env python3
"""Register CF directly from the exact detached CE authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_cf_replacement_recovery as cf_replacement

successor.STATE = cf_replacement.replacement.STATE / "registration-cf"
successor.AV_ID = "8cf0c597-cf81-4fa5-b1ff-f27e3537a94c"
successor.AV_GENERATION = "88996259-ad79-4aa6-962c-c29a24559db8"
successor.LOCK = "sha256:672e44b9964c3d284028abd6af01fdbc6e2eeb81fa732e68a88061d28331a214"
successor.CONFIG = {"configurationId": "13d3db4e-df8a-46c9-95c1-5a84ba01b896", "revision": 1,
                    "hash": "sha256:5e0b8d605a52f970f887ba60c60b73392962555b53d44564e017af6aae37d0e1"}
successor.AU_ID = "29d1b06d-3baa-4476-9cf8-5ea345d134c7"
successor.AU_GENERATION = "e51d0010-d57f-4f5c-8f7e-7a1d732bebf7"
successor.DETACH = "d626046d-ceae-402e-8fbe-51ebe87b1409"
successor.DETACH_HASH = "sha256:ffa929f43cc570edf7029abec398fe03c52cd06b4d3fd8fdb7a0a7fd5ede3981"
successor.KEY = "a0v-qyh-clean-generation-cf-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 218
successor.PREDECESSOR_GROUP_REVISION = 245
successor.replacement_module = lambda: cf_replacement.replacement

CF_ID = successor.AV_ID
CF_GENERATION = successor.AV_GENERATION
AV_ID = CF_ID
AV_GENERATION = CF_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = cf_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = cf_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = cf_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment
        def configure_cf():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                cf_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")
        launcher.configure_environment = configure_cf
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
            scope=scope, installation_id=CF_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact CF registration readback required")
    result = {"outcome": "CURRENT_CF_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_CF_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

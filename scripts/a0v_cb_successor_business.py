#!/usr/bin/env python3
"""Register CB directly from the exact detached CA authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_cb_replacement_recovery as cb_replacement

successor.STATE = cb_replacement.replacement.STATE / "registration-cb"
successor.AV_ID = "3d6df614-5a05-4c6f-823e-688d81e84096"
successor.AV_GENERATION = "0cceac8c-c831-4b3f-92c3-fc35240c5414"
successor.LOCK = "sha256:658b48f2444dfd18c6c42bbbadd22a7952063c60b6bae95d7384c6841ab9d3f7"
successor.CONFIG = {"configurationId": "76a01ce7-4c6c-406e-bc4e-a52cd957240c", "revision": 1,
                    "hash": "sha256:aa4cf1ee80739db6f487f95ac2226e18b7bf1d8cb709082303e078ae6c3c81a7"}
successor.AU_ID = "0d834ab1-fd2b-4dbc-b9a5-0f0dee712647"
successor.AU_GENERATION = "1f18a077-12c6-4242-982a-0c3fa1159540"
successor.DETACH = "bfffc7e7-5606-4101-9b5e-bc729ddb26ef"
successor.DETACH_HASH = "sha256:f4178b7c27dc9addc0fe17a13f446302af66d291960cd1c7a8aae6aab98554ce"
successor.KEY = "a0v-qyh-clean-generation-cb-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 206
successor.PREDECESSOR_GROUP_REVISION = 233
successor.replacement_module = lambda: cb_replacement.replacement

CB_ID = successor.AV_ID
CB_GENERATION = successor.AV_GENERATION
AV_ID = CB_ID
AV_GENERATION = CB_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = cb_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = cb_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = cb_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment
        def configure_cb():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                cb_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")
        launcher.configure_environment = configure_cb
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
            scope=scope, installation_id=CB_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact CB registration readback required")
    result = {"outcome": "CURRENT_CB_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_CB_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

from copy import deepcopy
from uuid import uuid4

import pytest

from aos_api.ecommerce_growth_registration_origin import RegistrationReceiptRef, verify_registration_origin
from aos_api.tenant_scope import TenantScope
from test_ecommerce_growth_registration_receipt import row


def inputs():
    value = row()
    request = value["payload"]["request"]
    return dict(row=value, scope=TenantScope("org-a", "project-a"),
        receipt_ref=RegistrationReceiptRef(resourceType="FirstDispatchRegistrationReceipt",
            resourceId=str(value["receipt_id"]), revision=1, contentHash=value["content_hash"]),
        dispatch_snapshot=deepcopy(value["payload"]["dispatchSnapshot"]),
        installation_id=value["payload"]["installationId"], generation=value["payload"]["generation"],
        execution_epoch=request["executionEpoch"], binding_revision=request["bindingRevision"])


def test_exact_origin_returns_detached_request_without_execution_authority():
    args = inputs(); before = deepcopy(args)
    result = verify_registration_origin(**args)
    assert result.request_hash() == args["row"]["request_hash"]
    assert result.model_dump(mode="json", by_alias=True) == args["row"]["payload"]["request"]
    assert args == before


@pytest.mark.parametrize("mutation", ["id", "hash", "scope", "installation", "generation",
    "epoch", "binding", "bool_epoch", "bool_binding", "partial", "extra", "fence", "revision", "mixed", "order"])
def test_drift_is_rejected(mutation):
    args = inputs()
    if mutation in ("id", "hash"):
        ref = args["receipt_ref"].model_dump()
        ref["resourceId" if mutation == "id" else "contentHash"] = str(uuid4()) if mutation == "id" else "sha256:" + "0" * 64
        args["receipt_ref"] = RegistrationReceiptRef.model_validate(ref)
    elif mutation == "scope": args["scope"] = TenantScope("other", "project-a")
    elif mutation in ("installation", "generation"): args["installation_id" if mutation == "installation" else "generation"] = str(uuid4())
    elif mutation in ("epoch", "binding", "bool_epoch", "bool_binding"):
        args["execution_epoch" if "epoch" in mutation else "binding_revision"] = True if mutation.startswith("bool") else 99
    elif mutation == "partial": args["dispatch_snapshot"].pop()
    elif mutation == "extra": args["dispatch_snapshot"].append(deepcopy(args["dispatch_snapshot"][0]))
    elif mutation == "order": args["dispatch_snapshot"].reverse()
    else:
        key = {"fence": "operationFence", "revision": "revision", "mixed": "handlerKind"}[mutation]
        args["dispatch_snapshot"][0][key] = {"fence": False, "revision": 2, "mixed": "extension"}[mutation]
    with pytest.raises(ValueError, match="REGISTRATION_ORIGIN_INVALID"):
        verify_registration_origin(**args)


@pytest.mark.parametrize("change", [{"revision": True}, {"revision": 2}, {"resourceType": "Other"}, {"resourceId": "bad"}, {"contentHash": "bad"}, {"unknown": 1}])
def test_exact_reference_shape(change):
    value = inputs()["receipt_ref"].model_dump(); value.update(change)
    with pytest.raises(ValueError): RegistrationReceiptRef.model_validate(value)

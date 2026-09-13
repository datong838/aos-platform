from uuid import uuid4

import pytest

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_growth_cutover import CutoverPrepareRequest, EcommerceGrowthCutoverStore, EcommerceGrowthCutoverBlocked
from aos_api.tenant_scope import TenantScope


def payload():
    ref = dict(resourceType="Policy", resourceId="policy", revision=1, contentHash="sha256:" + "a" * 64)
    return dict(cutoverOperationId=uuid4(), idempotencyKey="first-cutover", cutoverGroupId=uuid4(),
        expectedGroupRevision=1, targetInstallationId=uuid4(), targetGeneration=uuid4(),
        targetExecutionEpoch=3, targetRuntimeRevision=4, policyRef=ref,
        approvalRef={**ref, "resourceType": "ActionApprovalEvent"}, checkpoint={})


def registration_ref():
    return dict(resourceType="FirstDispatchRegistrationReceipt", resourceId=str(uuid4()),
                revision=1, contentHash="sha256:" + "b" * 64)


def test_legacy_hash_excludes_only_new_optional_field():
    request = CutoverPrepareRequest(**payload())
    legacy = request.model_dump(mode="json", by_alias=True)
    legacy.pop("registrationReceiptRef", None)
    assert request.request_hash() == canonical_sha256(legacy)
    assert "occurrenceWatermark" in legacy and legacy["occurrenceWatermark"] is None
    explicit_null = CutoverPrepareRequest(**payload(), registrationReceiptRef=None)
    expected = explicit_null.model_dump(mode="json", by_alias=True)
    expected.pop("registrationReceiptRef", None)
    assert explicit_null.request_hash() == canonical_sha256(expected)


def test_registration_reference_changes_hash_and_roundtrips():
    original = payload(); ref = registration_ref()
    plain = CutoverPrepareRequest(**original)
    request = CutoverPrepareRequest(**original, registrationReceiptRef=ref)
    assert request.request_hash() != plain.request_hash()
    assert request.registration_receipt_ref.model_dump() == ref
    assert CutoverPrepareRequest.model_validate_json(request.model_dump_json(by_alias=True)).request_hash() == request.request_hash()
    changed = CutoverPrepareRequest(**original, registrationReceiptRef={**ref, "contentHash": "sha256:" + "c" * 64})
    assert changed.request_hash() != request.request_hash()


@pytest.mark.parametrize("change", [{"revision": True}, {"revision": 2}, {"resourceId": "bad"}, {"unknown": 1}])
def test_invalid_origin_reference_is_rejected(change):
    with pytest.raises(ValueError):
        CutoverPrepareRequest(**payload(), registrationReceiptRef={**registration_ref(), **change})


def test_unwired_first_activation_never_opens_connection():
    def connect(_scope):
        pytest.fail("unwired registration activation opened a connection")
    store = EcommerceGrowthCutoverStore(connect)
    request = CutoverPrepareRequest(**payload(), registrationReceiptRef=registration_ref())
    with pytest.raises(EcommerceGrowthCutoverBlocked, match="registration activation"):
        store.prepare_activation(TenantScope("org-org", "dev-project"), request, actor="owner")

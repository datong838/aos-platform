"""W-L11 ProductionContext four-contract freeze."""
from __future__ import annotations

import uuid

import pytest

from aos_api.aip_production_contract_store import (
    AipProductionContractStore,
    ProductionContractDependencyBlocked,
)
from aos_api.aip_production_contracts import (
    ExactRevisionRef,
    FreezeProductionContextRequest,
    RevokeEvidenceBundleRequest,
)
from test_w2d_store import SCOPE, HASHES, _seed


def test_freeze_production_context_cas_and_rejects_drifted_bundle() -> None:
    preview_body, _ = _seed()
    store = AipProductionContractStore(
        production_profile_resolver=lambda scope, ref: True
    )
    key = f"ctx-{uuid.uuid4().hex}"
    req = FreezeProductionContextRequest(
        task_id=preview_body.task_id,
        brief_ref=preview_body.brief_ref,
        evidence_bundle_ref=preview_body.evidence_bundle_ref,
        eval_contract_ref=preview_body.eval_contract_ref,
        responsibility_plan_ref=preview_body.responsibility_plan_ref,
    )
    first = store.freeze_production_context(SCOPE, "test:w-l11", key, req)
    replay = store.freeze_production_context(SCOPE, "test:w-l11", key, req)
    assert first.context_id == replay.context_id
    assert first.content_hash == replay.content_hash
    assert first.lifecycle.value == "frozen"
    assert first.readiness.value == "ready"
    listing = store.list_production_contexts(SCOPE)
    assert any(item.context_id == first.context_id for item in listing.items)
    drifted = req.model_copy(
        update={
            "evidence_bundle_ref": ExactRevisionRef(
                resource_type="EvidenceBundleRevision",
                resource_id=preview_body.evidence_bundle_ref.resource_id,
                revision=1,
                content_hash="e" * 64,
            )
        }
    )
    with pytest.raises(ProductionContractDependencyBlocked):
        store.freeze_production_context(
            SCOPE, "test:w-l11", f"ctx-bad-{uuid.uuid4().hex}", drifted
        )


def test_freeze_rejects_revoked_bundle() -> None:
    preview_body, _ = _seed()
    store = AipProductionContractStore()
    store.revoke_evidence_bundle(
        SCOPE,
        "test:w-l11",
        preview_body.evidence_bundle_ref.resource_id,
        f"revoke-{uuid.uuid4().hex}",
        RevokeEvidenceBundleRequest(
            expected_revision=preview_body.evidence_bundle_ref.revision,
            expected_content_hash=HASHES["bundle"],
            reason="stale for context freeze",
        ),
    )
    with pytest.raises(ProductionContractDependencyBlocked):
        store.freeze_production_context(
            SCOPE,
            "test:w-l11",
            f"ctx-revoked-{uuid.uuid4().hex}",
            FreezeProductionContextRequest(
                task_id=preview_body.task_id,
                brief_ref=preview_body.brief_ref,
                evidence_bundle_ref=preview_body.evidence_bundle_ref,
                eval_contract_ref=preview_body.eval_contract_ref,
                responsibility_plan_ref=preview_body.responsibility_plan_ref,
            ),
        )


def test_freeze_retains_exact_production_profile_provenance() -> None:
    preview_body, _ = _seed()
    store = AipProductionContractStore(
        production_profile_resolver=lambda scope, ref: True
    )
    profile_ref = ExactRevisionRef(
        resource_type="ProductionProfileRevision",
        resource_id=(
            "bundle://aos/solution.ecommerce.growth@1.4.0/"
            "content/production-profiles/ecommerce.content-campaign.json"
        ),
        revision=7,
        content_hash="9" * 64,
    )
    result = store.freeze_production_context(
        SCOPE,
        "test:w3-04",
        f"ctx-profile-{uuid.uuid4().hex}",
        FreezeProductionContextRequest(
            task_id=preview_body.task_id,
            brief_ref=preview_body.brief_ref,
            evidence_bundle_ref=preview_body.evidence_bundle_ref,
            eval_contract_ref=preview_body.eval_contract_ref,
            responsibility_plan_ref=preview_body.responsibility_plan_ref,
            production_profile_ref=profile_ref,
        ),
    )
    assert result.production_profile_ref == profile_ref
    assert result.dependency_snapshot[-1] == {
        "resourceType": "ProductionProfileRevision",
        "resourceId": profile_ref.resource_id,
        "expectedRevision": profile_ref.revision,
        "expectedHash": profile_ref.content_hash,
        "authority": "active-installation",
        "resolved": True,
    }


def test_freeze_rejects_unresolved_production_profile() -> None:
    preview_body, _ = _seed()
    profile_ref = ExactRevisionRef(
        resource_type="ProductionProfileRevision",
        resource_id="bundle://aos/example@1.0.0/profile.json",
        revision=1,
        content_hash="8" * 64,
    )
    store = AipProductionContractStore(
        production_profile_resolver=lambda scope, ref: False
    )
    with pytest.raises(
        ProductionContractDependencyBlocked,
        match="PRODUCTION_PROFILE_MISSING_OR_DRIFTED",
    ):
        store.freeze_production_context(
            SCOPE,
            "test:w3-04",
            f"ctx-profile-blocked-{uuid.uuid4().hex}",
            FreezeProductionContextRequest(
                task_id=preview_body.task_id,
                brief_ref=preview_body.brief_ref,
                evidence_bundle_ref=preview_body.evidence_bundle_ref,
                eval_contract_ref=preview_body.eval_contract_ref,
                responsibility_plan_ref=preview_body.responsibility_plan_ref,
                production_profile_ref=profile_ref,
            ),
        )

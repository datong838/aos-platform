"""Cryptographically valid fixture policy must still prove exact Rule sources."""
import json

import pytest

from aos_api.aip_production_contract_store import AipProductionContractStore, ProductionContractDependencyBlocked
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.composition_contracts import StoredCompositionLock
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.extension_runtime.current_installation_release_evidence import (
    CurrentReleaseEvidenceBlocked, _read_unique_active_in_transaction,
)
from tests.asset_registry.test_qyh_installation_source_pg import installed  # noqa: F401
from tests.asset_registry.test_qyh_complete_media_source_pg import complete_case, SCOPE  # noqa: F401
from tests.asset_registry.test_m5_ecommerce_composition_installation_pg import OVERLAY_FIXTURE, _three_leaf_request


@pytest.mark.parametrize("complete_case", ["ruleDigestMismatch", "testOnlyRule"], indirect=True)
def test_original_signed_policy_still_rejects_invalid_rule_source(complete_case):
    store, factory, reader, body, admin, runtime = complete_case
    bundle = runtime.prepared.by_id("solution.ecommerce.growth").signed
    loaded = runtime.prepared.loader.load(runtime.prepared.by_id("solution.ecommerce.growth").fixture.source_ref)
    assert loaded.content_hash == bundle.content_hash
    artifact = next(a for a in loaded.artifacts if a.relative_path == "content/media-gate-policies/full.json")
    assert artifact.digest[7:] == body.policy_ref.content_hash
    assert json.loads(runtime.prepared.loader.read_verified_artifact(
        runtime.prepared.by_id("solution.ecommerce.growth").fixture.source_ref,
        artifact.relative_path, expected_digest=artifact.digest, limit=32768,
    ))["gates"] == [g.model_dump(mode="json", by_alias=True, exclude={"hard_block", "allow_override"}) for g in body.gates]
    # Prove actual signature publication and exact installation are valid,
    # rather than accepting a negative caused by an unrelated missing source.
    material = runtime.registry_service.get_published_reference_material(
        publisher="aos", bundle_id=bundle.manifest.metadata.id, version=bundle.manifest.metadata.version,
    )
    assert material["contentHash"][7:] == body.source_bundle_ref.content_hash
    reference = body.gates[0].rule_ref
    row = admin.execute(
        "SELECT content_hash FROM public.aip_review_rule_revision WHERE org_id=%s AND project_id=%s AND rule_id=%s AND revision=%s",
        (*SCOPE.key, reference.resource_id, reference.revision),
    ).fetchone()
    with factory(SCOPE) as conn:
        view = _read_unique_active_in_transaction(
            conn._raw, scope=SCOPE, publisher="aos", bundle_id=bundle.manifest.metadata.id,
            version=bundle.manifest.metadata.version, content_hash=bundle.content_hash,
            release_policy=ReleasePolicy(trust_roots=runtime.prepared.trust_roots), loader=runtime.prepared.loader,
        )
        assert view.scope == SCOPE.key and view.current_revision == view.active_revision
        rules = AipProductionContractStore()
        if row["content_hash"] != reference.content_hash:
            with pytest.raises(ProductionContractDependencyBlocked, match="REVIEW_RULE_CONTENT_DRIFTED"):
                rules.get_review_rule_revision_with_content_integrity(SCOPE, reference, conn=conn)
            corrected = reference.model_copy(update={"content_hash": row["content_hash"]})
            assert rules.get_review_rule_revision_with_content_integrity(SCOPE, corrected, conn=conn).spec["testOnly"] is False
        else:
            assert rules.get_review_rule_revision_with_content_integrity(SCOPE, reference, conn=conn).spec["testOnly"] is True
        assert reader(conn, SCOPE, body) is False
    with pytest.raises(ProductionContractDependencyBlocked):
        store.register_media_gate_profile(SCOPE, "fixture-source-maker", "invalid-signed-rule-" + reference.resource_id, body)
    assert admin.execute("SELECT count(*) AS n FROM public.aip_media_gate_profile_revision WHERE profile_id=%s", (body.profile_id,)).fetchone()["n"] == 0


def test_two_original_active_installations_reject_persisted_profile_replay(complete_case):
    store, factory, reader, body, admin, runtime = complete_case
    key = "ambiguous-profile-source"
    original = store.register_media_gate_profile(SCOPE, "fixture-source-maker", key, body)
    resolved = runtime.resolve(_three_leaf_request(runtime.snapshot_reader.read()), actor="fixture-maker", idempotency_key="ambiguous-resolve")
    lock = StoredCompositionLock.model_validate_json(json.dumps(resolved.response_json))
    runtime.install_to_active(
        lock=lock, overlay_revision=canonical_sha256(json.loads(OVERLAY_FIXTURE.read_text())),
        maker="fixture-maker", checker="fixture-checker", idempotency_prefix="ambiguous-second-install",
    )
    bundle = runtime.prepared.by_id("solution.ecommerce.growth").signed
    with factory(SCOPE) as conn:
        with pytest.raises(CurrentReleaseEvidenceBlocked, match="ACTIVE_INSTALLATION_AMBIGUOUS"):
            _read_unique_active_in_transaction(
                conn._raw, scope=SCOPE, publisher="aos", bundle_id=bundle.manifest.metadata.id,
                version=bundle.manifest.metadata.version, content_hash=bundle.content_hash,
                release_policy=ReleasePolicy(trust_roots=runtime.prepared.trust_roots), loader=runtime.prepared.loader,
            )
        assert reader(conn, SCOPE, body) is False
    with pytest.raises(ProductionContractDependencyBlocked):
        store.register_media_gate_profile(SCOPE, "fixture-source-maker", key, body)
    assert original.profile_id == body.profile_id
    assert admin.execute("SELECT count(*) AS n FROM public.aip_media_gate_profile_revision WHERE profile_id=%s", (body.profile_id,)).fetchone()["n"] == 1
    assert admin.execute("SELECT count(*) AS n FROM public.aip_production_contract_receipt WHERE operation='media_gate_profile.register' AND idempotency_key=%s", (key,)).fetchone()["n"] == 1

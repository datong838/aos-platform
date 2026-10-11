"""Real source invalidation in disposable control plane; no runtime start."""
import base64
import json

import psycopg
import pytest

from aos_api.aip_production_contract_store import ProductionContractDependencyBlocked
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.composition_contracts import (
    InstallationResponse, RollbackInstallationRequest, StoredCompositionLock,
)
from aos_api.asset_registry.manifest_loader import SIGNATURE_FILENAME
from tests.asset_registry.test_qyh_installation_source_pg import installed  # noqa: F401
from tests.asset_registry.test_qyh_complete_media_source_pg import complete_case, SCOPE  # noqa: F401
from tests.asset_registry.test_m5_ecommerce_composition_installation_pg import (
    OVERLAY_FIXTURE, _three_leaf_request,
)


@pytest.mark.parametrize("artifact_kind", ["policy", "signature"])
def test_signed_artifact_tamper_invalidates_source_and_no_registration(complete_case, artifact_kind):
    store, factory, reader, body, admin, runtime = complete_case
    with factory(SCOPE) as conn:
        assert reader(conn, SCOPE, body) is True
    bundle = runtime.prepared.by_id("solution.ecommerce.growth")
    path = bundle.bundle_path / (
        "content/media-gate-policies/full.json" if artifact_kind == "policy" else SIGNATURE_FILENAME
    )
    original = path.read_bytes()
    try:
        if artifact_kind == "policy":
            path.write_bytes(original + b"\n ")
        else:
            envelope = json.loads(original)
            envelope["signature"] = base64.b64encode(bytes(64)).decode()
            path.write_text(json.dumps(envelope))
        with factory(SCOPE) as conn:
            assert reader(conn, SCOPE, body) is False
        with pytest.raises(ProductionContractDependencyBlocked):
            store.register_media_gate_profile(SCOPE, "fixture-source-maker", "tampered-" + artifact_kind, body)
        assert admin.execute(
            "SELECT count(*) AS n FROM public.aip_media_gate_profile_revision WHERE profile_id=%s",
            (body.profile_id,),
        ).fetchone()["n"] == 0
        assert admin.execute(
            "SELECT count(*) AS n FROM public.aip_production_contract_receipt WHERE operation='media_gate_profile.register' AND idempotency_key=%s",
            ("tampered-" + artifact_kind,),
        ).fetchone()["n"] == 0
    finally:
        path.write_bytes(original)
    with factory(SCOPE) as conn:
        assert reader(conn, SCOPE, body) is True


def test_original_rule_persisted_contents_cannot_be_overwritten(complete_case):
    _, factory, reader, body, admin, _ = complete_case
    reference = body.gates[0].rule_ref
    query = "SELECT spec,content_hash FROM public.aip_review_rule_revision WHERE org_id=%s AND project_id=%s AND rule_id=%s AND revision=%s"
    params = (*SCOPE.key, reference.resource_id, reference.revision)
    before = admin.execute(query, params).fetchone()
    with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState) as blocked:
        admin.execute(
            "UPDATE public.aip_review_rule_revision SET spec='{}'::jsonb WHERE org_id=%s AND project_id=%s AND rule_id=%s AND revision=%s",
            params,
        )
    assert blocked.value.diag.message_primary == "AIP4_APPEND_ONLY"
    assert admin.execute(query, params).fetchone() == before
    with factory(SCOPE) as conn:
        assert reader(conn, SCOPE, body) is True


def test_original_installation_rollback_fences_old_receipt_and_new_install_recovers(complete_case):
    store, factory, reader, body, admin, runtime = complete_case
    key = "installation-invalidation"
    registered = store.register_media_gate_profile(SCOPE, "fixture-source-maker", key, body)
    with factory(SCOPE) as conn:
        from aos_api.extension_runtime.current_installation_release_evidence import _read_unique_active_in_transaction
        from aos_api.asset_registry.release_policy import ReleasePolicy
        bundle = runtime.prepared.by_id("solution.ecommerce.growth").signed
        old = _read_unique_active_in_transaction(
            conn._raw, scope=SCOPE, publisher="aos", bundle_id=bundle.manifest.metadata.id,
            version=bundle.manifest.metadata.version, content_hash=bundle.content_hash,
            release_policy=ReleasePolicy(trust_roots=runtime.prepared.trust_roots), loader=runtime.prepared.loader,
        )
    receipt = runtime.installation_service.rollback(
        installation_id=old.installation_id, request=RollbackInstallationRequest(reason="isolated source invalidation"),
        org_id=SCOPE.org_id, project_id=SCOPE.project_id, actor="fixture-maker",
        roles={"asset-installer"}, markings=set(), idempotency_key="original-install-rollback", if_match='"5"',
    )
    rolled_back = InstallationResponse.model_validate_json(json.dumps(receipt.response_json))
    assert rolled_back.state == "rolled_back" and rolled_back.current_revision == 6
    assert rolled_back.active_revision is None
    with factory(SCOPE) as conn:
        assert reader(conn, SCOPE, body) is False
    # A previously persisted result must not bypass freshly failed Source.
    with pytest.raises(ProductionContractDependencyBlocked):
        store.register_media_gate_profile(SCOPE, "fixture-source-maker", key, body)
    resolved = runtime.resolve(
        _three_leaf_request(runtime.snapshot_reader.read()), actor="fixture-maker", idempotency_key="reinstall-resolve",
    )
    lock = StoredCompositionLock.model_validate_json(json.dumps(resolved.response_json))
    installed_receipts = runtime.install_to_active(
        lock=lock, overlay_revision=canonical_sha256(json.loads(OVERLAY_FIXTURE.read_text())),
        maker="fixture-maker", checker="fixture-checker", idempotency_prefix="new-original-install",
    )
    current = InstallationResponse.model_validate_json(json.dumps(installed_receipts[-1].response_json))
    assert str(current.installation_id) != old.installation_id
    assert current.state == "active" and current.current_revision == 5
    with factory(SCOPE) as conn:
        assert reader(conn, SCOPE, body) is True
    assert store.register_media_gate_profile(SCOPE, "fixture-source-maker", key, body) == registered
    assert admin.execute(
        "SELECT count(*) AS n FROM public.aip_production_contract_receipt WHERE operation='media_gate_profile.register' AND idempotency_key=%s",
        (key,),
    ).fetchone()["n"] == 1

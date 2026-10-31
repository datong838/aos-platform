from datetime import timedelta

import pytest
from pydantic import SecretStr

from aos_api.aip_model_route_eval_finalization_proof import RouteEvalFinalizationProofStore
from aos_api.aip_model_route_eval_proof_authority import VerifiedRouteEvalReleaseEvidence
from aos_api.aip_model_route_eval_release_material import (
    RouteEvalReleaseAssemblyRejected,
    RouteEvalReleaseEvidenceAssembler,
    RouteEvalReleaseMaterialRejected,
    read_verified_route_eval_release_material,
)
from aos_api.aip_route_release_request_context import RouteReleaseRequestContext
from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_contracts import TenantContext
from aos_api.aip_eval_contracts import AssetRevisionRef, AssetType
from aos_api.aip_model_runtime_contracts import (
    ModelModality, ModelRouteCandidate, ModelRouteRevision,
    ModelRuntimeLifecycle, RouteStrategy,
)
from aos_api.aip_model_runtime_store import evaluation_candidate_ref
from aos_api.aip_release_publication_service import (
    AipReleaseGateRejected,
    AipReleasePublicationService,
)
from aos_api.auth import Principal
from aos_api.tenant_scope import TenantScope
from test_model_route_eval_finalization_proof import NOW, ProofConnection, finalization_fixture
from test_model_route_eval_atomic_finalizer import fixture as atomic_fixture


SCOPE = TenantScope("org-org", "dev-project")


def persisted_fixture():
    proof, manifest, target, judge, journal = finalization_fixture()
    conn = ProofConnection(proof)
    store = RouteEvalFinalizationProofStore(journal=journal)
    store.persist(conn, SCOPE, proof, manifest_bytes=manifest,
        presented_cases=(target, judge), checked_at=NOW + timedelta(seconds=2),
        revoked_identity_ids=frozenset())
    return conn, proof, manifest


def test_reads_all_and_only_business_sources_from_persisted_release_material():
    conn, proof, manifest = persisted_fixture()
    result = read_verified_route_eval_release_material(conn, scope=SCOPE, proof=proof)
    assert result.execution_id == proof.execution_id
    assert result.manifest_hash == proof.manifest_hash
    assert result.manifest_bytes == manifest
    assert [item.asset_id for item in result.sources] == ["source-judge", "source-target"]
    assert result.execution_allowed is False


@pytest.mark.parametrize("fault", ["missing", "payload", "hash", "proof_calls"])
def test_release_material_reader_fails_closed_on_missing_or_drifted_business_source(fault):
    conn, proof, manifest = persisted_fixture()
    if fault == "missing":
        conn.material = None
    elif fault == "payload":
        conn.material["manifest_payload"] = manifest + b"\n"
    elif fault == "hash":
        conn.material["manifest_hash"] = "0" * 64
    else:
        proof = proof.model_copy(update={"calls": proof.calls[:1]})
    with pytest.raises(RouteEvalReleaseMaterialRejected):
        read_verified_route_eval_release_material(conn, scope=SCOPE, proof=proof)


def test_release_assembler_keeps_source_commands_ephemeral_and_returns_only_verified(monkeypatch):
    proof, manifest, presented, journal, report, _, _ = atomic_fixture()
    conn = ProofConnection(proof)
    RouteEvalFinalizationProofStore(journal=journal).persist(
        conn, SCOPE, proof, manifest_bytes=manifest, presented_cases=presented,
        checked_at=NOW + timedelta(seconds=2), revoked_identity_ids=frozenset())
    context = RouteReleaseRequestContext(
        principal=Principal(subject="operator", org_id="org-org",
            project_id="dev-project", token_kind="oidc"),
        bearer_token=SecretStr("header.payload.signature"),
    )
    seen = {}
    verified = VerifiedRouteEvalReleaseEvidence(
        execution_id=proof.execution_id, report_id=report.report_id,
        report_hash=report.content_hash, manifest_hash=proof.manifest_hash,
        source_count=2, publication_epoch=1,
        checked_at=NOW + timedelta(seconds=4), caller_xid="42", caller_pid=84)

    def read_report(_conn, *, scope, report):
        assert scope == SCOPE
        return type("ReportProof", (), {"proof": proof})()

    def verify(_conn, *, scope, report, evidence, publication_id=None):
        seen["scope"] = scope
        seen["report"] = report
        seen["evidence"] = evidence
        seen["publication_id"] = publication_id
        return verified

    monkeypatch.setattr(
        "aos_api.aip_model_route_eval_report_proof_reader."
        "read_verified_route_eval_report_from_persistence", read_report)
    monkeypatch.setattr(
        "aos_api.aip_model_route_eval_proof_authority."
        "verify_route_eval_release_evidence", verify)
    result = RouteEvalReleaseEvidenceAssembler().verify(
        conn, scope=SCOPE, report=report, request_context=context,
        publication_id="publication-1")
    assert result is verified
    evidence = seen["evidence"]
    assert evidence.manifest_bytes == manifest
    assert [item.source_ref.asset_id for item in evidence.source_commands] == [
        "source-judge", "source-target"]
    assert all(item.bearer_token.get_secret_value() == "header.payload.signature"
        for item in evidence.source_commands)
    assert seen["publication_id"] == "publication-1"
    assert "header.payload.signature" not in repr(result)


def test_route_assembler_uses_exact_current_gate_and_report_lineage(monkeypatch):
    tenant = TenantContext(org_id=SCOPE.org_id, project_id=SCOPE.project_id)
    ref = lambda kind, identity, digest: VersionedAssetRef(
        assetType=kind, assetId=identity, revision=1, contentHash=digest)
    route = ModelRouteRevision(tenant=tenant, routeId="route", revision=2,
        contentHash="1" * 64, taskTypes=["copy.generate"],
        requiredInputModality=ModelModality.TEXT,
        requiredOutputModality=ModelModality.TEXT,
        candidates=[ModelRouteCandidate(model=ref(
            "RegisteredModelRevision", "model", "2" * 64))],
        strategy=RouteStrategy.FAILOVER,
        runtimePolicyRef=ref("RuntimePolicyRevision", "policy", "3" * 64),
        evalGateRef=VersionedAssetRef(assetType="EvalGateDecision",
            assetId="gate", revision=1, contentHash="4" * 64),
        lifecycle=ModelRuntimeLifecycle.ACTIVE, createdBy="test", createdAt=NOW)
    target_ref = evaluation_candidate_ref(route)
    target = AssetRevisionRef(assetType=AssetType.MODEL_ROUTE,
        assetId=target_ref.asset_id, revision=str(target_ref.revision),
        contentHash=target_ref.content_hash)
    gate = type("Gate", (), {
        "decision_hash": "4" * 64, "target": target,
        "eval_report": type("ReportRef", (), {
            "artifact_id": "report", "revision": "1",
            "content_hash": "5" * 64})(),
    })()
    report = type("Report", (), {"content_hash": "5" * 64,
        "target": target})()
    rows = [{"gate": True}, {"report": True}]
    class Conn:
        def execute(self, *_args, **_kwargs):
            return type("Rows", (), {"fetchone": lambda self: rows.pop(0)})()
    monkeypatch.setattr(AipReleasePublicationService, "_gate_from_row",
        staticmethod(lambda *_: gate))
    monkeypatch.setattr(AipReleasePublicationService, "_report_from_row",
        staticmethod(lambda *_: report))
    sentinel = object()
    monkeypatch.setattr(RouteEvalReleaseEvidenceAssembler, "build",
        lambda self, conn, **kwargs: sentinel)
    context = RouteReleaseRequestContext(
        principal=Principal(subject="worker", org_id="org-org",
            project_id="dev-project", token_kind="oidc"),
        bearer_token=SecretStr("header.payload.signature"))
    assert RouteEvalReleaseEvidenceAssembler().build_for_route(
        Conn(), scope=SCOPE, route=route, request_context=context) is sentinel


@pytest.mark.parametrize("fault", ["context", "scope", "publication"])
def test_release_assembler_rejects_noncurrent_request_without_verifier_call(monkeypatch, fault):
    _, _, _, _, report, _, _ = atomic_fixture()
    context = RouteReleaseRequestContext(
        principal=Principal(subject="operator", org_id="org-org",
            project_id="dev-project", token_kind="oidc"),
        bearer_token=SecretStr("header.payload.signature"),
    )
    called = []
    monkeypatch.setattr(
        "aos_api.aip_model_route_eval_proof_authority."
        "verify_route_eval_release_evidence", lambda *a, **k: called.append(True))
    with pytest.raises(RouteEvalReleaseAssemblyRejected):
        RouteEvalReleaseEvidenceAssembler().verify(
            object(), scope=TenantScope("dev-org", "dev-project") if fault == "scope" else SCOPE,
            report=report, request_context=object() if fault == "context" else context,
            publication_id=" bad" if fault == "publication" else None)
    assert called == []


def test_release_service_uses_request_context_without_returning_secret_evidence(monkeypatch):
    proof, _, _, _, report, _, _ = atomic_fixture()
    context = RouteReleaseRequestContext(
        principal=Principal(subject="operator", org_id="org-org",
            project_id="dev-project", token_kind="oidc"),
        bearer_token=SecretStr("header.payload.signature"),
    )
    verified = VerifiedRouteEvalReleaseEvidence(
        execution_id=proof.execution_id, report_id=report.report_id,
        report_hash=report.content_hash, manifest_hash=proof.manifest_hash,
        source_count=2, publication_epoch=1,
        checked_at=NOW + timedelta(seconds=4), caller_xid="42", caller_pid=84)
    seen = {}

    def assemble(_self, conn, *, scope, report, request_context,
            publication_id=None):
        seen.update(conn=conn, scope=scope, report=report,
            request_context=request_context, publication_id=publication_id)
        return verified

    monkeypatch.setattr(RouteEvalReleaseEvidenceAssembler, "verify", assemble)
    result = AipReleasePublicationService._verify_route_release(
        object(), SCOPE, report, None, publication_id="publication-1",
        request_context=context)
    assert result is None
    assert seen["request_context"] is context
    assert seen["publication_id"] == "publication-1"
    assert "header.payload.signature" not in repr(seen)


def test_release_service_rejects_ambiguous_or_missing_route_authority():
    _, _, _, _, report, _, _ = atomic_fixture()
    context = RouteReleaseRequestContext(
        principal=Principal(subject="operator", org_id="org-org",
            project_id="dev-project", token_kind="oidc"),
        bearer_token=SecretStr("header.payload.signature"),
    )
    with pytest.raises(AipReleaseGateRejected):
        AipReleasePublicationService._verify_route_release(
            object(), SCOPE, report, None)
    with pytest.raises(AipReleaseGateRejected):
        AipReleasePublicationService._verify_route_release(
            object(), SCOPE, report, object(), request_context=context)

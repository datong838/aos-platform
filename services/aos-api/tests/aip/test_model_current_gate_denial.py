"""Current consumers fail closed until typed Model execution is supported."""
from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_contracts import ArtifactRef, TenantContext
from aos_api.aip_eval_contracts import AssetRevisionRef, AssetType, ReleaseGateDecision
from aos_api.aip_eval_authority_store import AipEvalAuthorityStore, AipEvalGateDependencyBlocked
from aos_api.aip_model_runtime_resolver import AipModelRuntimeResolver
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 10, 8, tzinfo=UTC)

def reader(kind):
    gate = ReleaseGateDecision(tenant=TenantContext(org_id=SCOPE.org_id, project_id=SCOPE.project_id),
        decision_id="synthetic-unsigned-gate", target=AssetRevisionRef(asset_type=kind,
            asset_id="target", revision="1", content_hash="2" * 64),
        suite_ref=AssetRevisionRef(asset_type=AssetType.EVAL_SUITE, asset_id="suite",
            revision="1", content_hash="3" * 64), eval_run_id="queued-no-execution",
        eval_report=ArtifactRef(artifact_id="absent-report", artifact_type="eval_report",
            revision="1", content_hash="4" * 64), status="passed", decision_hash="1" * 64,
        decided_by="test-only", decided_at=NOW)
    row = gate.model_dump()
    row["target_ref"] = row.pop("target")
    row["eval_report_ref"] = row.pop("eval_report")
    class Connection:
        def execute(self, query, params):
            assert query.lstrip().startswith("SELECT * FROM aip_release_gate_decision")
            return self
        def fetchone(self): return row
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield Connection()
    return AipEvalAuthorityStore(connect), connect, gate

@pytest.mark.parametrize("kind, ref_kind", [(AssetType.REGISTERED_MODEL, "RegisteredModelRevision"),
    (AssetType.MODEL_ROUTE, "ModelRouteRevision")])
@pytest.mark.parametrize("bind_target", [False, True])
def test_current_reader_rejects_unsupported_model_proof(kind, ref_kind, bind_target):
    store, connect, gate = reader(kind)
    ref = VersionedAssetRef(assetType="EvalGateDecision", assetId=gate.decision_id,
        revision=1, contentHash=gate.decision_hash)
    target = VersionedAssetRef(assetType=ref_kind, assetId="target", revision=1, contentHash="2" * 64)
    with pytest.raises(AipEvalGateDependencyBlocked, match="signed execution"):
        store.require_exact_passed(SCOPE, ref, expected_target=target if bind_target else None, now=NOW)
    resolver = AipModelRuntimeResolver(SimpleNamespace(_connect_factory=connect, _eval_authority_store=store))
    assert resolver._gate_passed(SCOPE, ref, target, NOW) is False

@pytest.mark.parametrize("kind", [AssetType.SKILL_TEMPLATE, AssetType.LOGIC_GRAPH])
def test_other_current_gate_reads_keep_original_behavior(kind):
    store, _, gate = reader(kind)
    ref = VersionedAssetRef(assetType="EvalGateDecision", assetId=gate.decision_id,
        revision=1, contentHash=gate.decision_hash)
    assert store.require_exact_passed(SCOPE, ref, now=NOW) == gate

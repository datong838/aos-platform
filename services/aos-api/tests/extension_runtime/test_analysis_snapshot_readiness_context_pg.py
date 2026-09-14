"""Actual two-source PG rejection; full canonical assembly is a named fixture."""
import pytest
from test_analysis_snapshot_business_evidence_pg import (
    database, pytestmark, ledger, owner_case, claim_case, executor_case,
    group_claim_case, prepared_case, assessment_case, journal_case, object_case,
    completed_group, bridge_case, business_case, fact_case, evidence_case,
    query_case, quality_case, business_evidence_case, inputs, revoke,
)
from aos_api.ecommerce_analysis_snapshot_readiness_context import AnalysisSnapshotReadinessContext


def test_actual_two_source_chain_cannot_claim_twelve(business_evidence_case):
    case, business, policy = business_evidence_case
    conn = case[0]
    ref = business.put_current(conn, **inputs(business_evidence_case))
    readiness = policy.model_copy(update={"resource_type": "SnapshotReadinessPolicy"})
    owner = AnalysisSnapshotReadinessContext(business)
    called = []
    with pytest.raises(ValueError, match="complete canonical"):
        owner.run_current(conn, business_ref=ref, policy_ref=readiness,
                          execute=lambda value: called.append(value))
    assert called == []


def test_revoked_business_rejected_before_readiness(business_evidence_case):
    case, business, policy = business_evidence_case
    conn, _, source = case[:3]
    ref = business.put_current(conn, **inputs(business_evidence_case))
    revoke(conn, source, ref)
    with pytest.raises(ValueError, match="revoked"):
        AnalysisSnapshotReadinessContext(business).run_current(
            conn, business_ref=ref, policy_ref=policy, execute=lambda _: None)


@pytest.fixture
def canonical_assembly():
    """Named pure composition fixture, not a current installation or database proof."""
    from datetime import UTC, datetime, timedelta
    from types import SimpleNamespace as NS
    from aos_api.tenant_scope import TenantScope
    from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
    from aos_api.source_readiness_contracts import CANONICAL_QYH_SOURCES, ExactResourceRef
    now = datetime(2026, 9, 15, tzinfo=UTC)
    def ref(kind):
        return PipelineExactRef(resource_type=kind, resource_id=kind, revision=1, content_hash='sha256:'+'a'*64)
    members, parents, counts, runs = [], [], [], {}
    for s in reversed(CANONICAL_QYH_SOURCES):
        draft = NS(source_id='niushop-qyh', pipeline_id=s.pipeline_id,
            source_configuration_ref=ref('DataSourceConfigurationRevision'), mapping_ref=ref('Mapping'),
            schema_ref=ref('SchemaFingerprint'), masking_policy_ref=ref('MaskingPolicy'))
        members.append((None, draft, NS(read_spec=NS(object_type=s.object_type))))
        parents.append(dict(runId=s.pipeline_id))
        counts.append(dict(pipelineId=s.pipeline_id, runId=s.pipeline_id, objectType=s.object_type,
            sourceTotal=1, sourceActive=1, sourceDeleted=0, projectedBaseTotal=1))
        runs[s.pipeline_id] = dict(run_id=s.pipeline_id, status='succeeded', finished_at=now)
    return dict(scope=TenantScope('org-org','dev-project'),
        original=NS(group=NS(members=members, expires_at=now+timedelta(minutes=30)), parents=parents,
            read_started_at=now-timedelta(seconds=1), read_completed_at=now),
        counts=dict(tenant=dict(orgId='org-org',projectId='dev-project'), members=counts), runs=runs,
        quality=NS(assessment=NS(reasons=(),freshness_expires_at=now+timedelta(hours=1))),
        business=dict(factIds=[s.object_type for s in CANONICAL_QYH_SOURCES]),
        field_ref=ref('SnapshotFactQualityPolicy'),policy_ref=ref('SnapshotReadinessPolicy'),
        binding=NS(binding_ref=ExactResourceRef(resource_type='CapabilityBinding', resource_id='fixture',
            revision='1',content_hash='b'*64,authority='fixture'),expires_at=now+timedelta(minutes=5)),
        checked_at=now)


def test_named_full_assembly_reorders_without_inventing_projection_time(canonical_assembly):
    from aos_api.ecommerce_analysis_snapshot_readiness_context import _assemble
    from aos_api.source_readiness import SourceReadinessService
    from aos_api.source_readiness_contracts import CANONICAL_QYH_PIPELINE_IDS
    value = _assemble(**canonical_assembly)
    assert tuple(s.pipeline_id for s in value.sources) == CANONICAL_QYH_PIPELINE_IDS
    assert all(s.freshness_expires_at == canonical_assembly['binding'].expires_at for s in value.sources)
    assert all(s.projected_at is None and s.source_event_at is None for s in value.sources)
    assert SourceReadinessService.evaluate_installed_snapshot(value).status == 'ready'


@pytest.mark.parametrize('reason,failed', [('QUALITY_BELOW_THRESHOLD:Weapp',1), ('POPULATION_BELOW_MINIMUM',12)])
def test_named_assembly_preserves_original_quality_reasons(canonical_assembly,reason,failed):
    from aos_api.ecommerce_analysis_snapshot_readiness_context import _assemble
    canonical_assembly['quality'].assessment.reasons=(reason,)
    assert sum(s.quality.status == 'fail' for s in _assemble(**canonical_assembly).sources)==failed


@pytest.mark.parametrize('fault',['missing-count','wrong-run','wrong-object','canary','missing-group'])
def test_named_assembly_rejects_mixed_provenance(canonical_assembly,fault):
    from aos_api.ecommerce_analysis_snapshot_readiness_context import _assemble
    data=canonical_assembly
    if fault=='missing-count':data['counts']['members'].pop()
    elif fault=='wrong-run':data['counts']['members'][0]['runId']='unrelated'
    elif fault=='wrong-object':data['counts']['members'][0]['objectType']='Other'
    elif fault=='canary':data['counts']['tenant']['orgId']='dev-org'
    elif fault=='missing-group':data['original'].parents.pop()
    with pytest.raises((ValueError,PermissionError)):_assemble(**data)

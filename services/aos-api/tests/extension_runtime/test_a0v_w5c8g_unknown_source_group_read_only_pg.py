"""Original unknown attempt must bind dual Receipts to one saved source group."""

from dataclasses import replace
import hashlib
from types import SimpleNamespace as NS

import pytest

pytest_plugins = ('test_analysis_snapshot_resume_chain_pg',)
pytestmark = [
    pytest.mark.parametrize('startup_case', ['defer-host'], indirect=True),
    pytest.mark.parametrize('stored', ['qualified-runtime'], indirect=True),
]

from aos_api.data_requirement_outbox_store import DataRequirementOutboxStore
from aos_api.data_requirement_store import DataRequirementStore
from aos_api.ecommerce_analysis_data_requirement_route import AnalysisDataRequirementRouteReader
from aos_api.ecommerce_analysis_snapshot_coordinator import AnalysisSnapshotCoordinator
from aos_api.ecommerce_analysis_snapshot_policy_set import AnalysisSnapshotPolicySetOwner
from aos_api.ecommerce_analysis_unknown_source_group_evidence import (
    UnknownSourceGroupEvidenceReader, UnknownSourceGroupFrozen,
)
from aos_api.tenant_scope import TenantScope
from test_a0v_w5c8d_original_attempt_receipt_resolver_pg import _factory


def test_unknown_original_receipts_and_saved_group_share_read_only_snapshot(chain_case, monkeypatch):
    conn, state, analysis, _session, _root, _requirement = chain_case
    conn.rollback()
    writer = _factory(conn, read_only=False)
    reader = _factory(conn, read_only=True)
    analysis.connect = writer
    claim = DataRequirementOutboxStore(writer).claim_next(analysis.scope,
        topic='data.requirement.request', worker_id='w5c8g-test',
        lease_token='w5c8g-original-token', lease_seconds=300)
    assert claim is not None
    route = AnalysisDataRequirementRouteReader(
        claims=analysis.source.reader._journal._claims, connect_factory=writer,
    ).read(analysis.scope, claim)
    artifacts = analysis.source.reader._journal._claims._controls._selections._artifacts
    old_record = artifacts.load_record
    documents = {path: artifacts.read_artifact(None, path, 256 * 1024)
        for _, path in AnalysisSnapshotPolicySetOwner.POLICIES}
    indexed = [dict(relativePath=path, digest='sha256:' + hashlib.sha256(raw).hexdigest(),
        size=len(raw), mediaType='application/json') for path, raw in documents.items()]
    artifacts.load_record = lambda selected: NS(manifest=old_record(selected).manifest, artifacts=indexed)
    result = AnalysisSnapshotCoordinator(analysis=analysis,
        completion=state['completion'], store=state['completion']._store).run(route=route)
    assert result['phase'] == 'RUNNING' and state['calls'] == 1
    DataRequirementOutboxStore(writer).mark_unknown(analysis.scope,
        claim.outbox_id, claim.lease_token, reason_code='W5C8G_DIAGNOSTIC_UNKNOWN')
    evidence_reader = UnknownSourceGroupEvidenceReader(
        claims=analysis.source.reader._journal._claims, connect_factory=reader,
    )
    evidence = evidence_reader.resolve(analysis.scope, claim)
    assert evidence.receipts.analysis_ref.receipt_id == result['receiptRef']['receiptId']
    assert evidence.source_group.group_id == route.group_id
    assert evidence.source_group.source_run_id == route.source_run_id
    assert evidence.source_group.group_bindings == route.group_bindings
    assert state['calls'] == 1
    def current_head_forbidden(*_args, **_kwargs):
        raise AssertionError('historical diagnostic must not consult current head')
    with monkeypatch.context() as change:
        change.setattr(DataRequirementStore, 'get_current', current_head_forbidden)
        assert evidence_reader.resolve(analysis.scope, claim).source_group.group_id == route.group_id
    original_read = AnalysisDataRequirementRouteReader.read_unknown_historical
    with monkeypatch.context() as change:
        change.setattr(AnalysisDataRequirementRouteReader, 'read_unknown_historical',
            lambda self, scope, frozen: replace(original_read(self, scope, frozen),
                source_run_id='wrong-w5c8g-source-run'))
        with pytest.raises(UnknownSourceGroupFrozen, match='ORIGINAL_SOURCE_GROUP_LINEAGE_DRIFT'):
            evidence_reader.resolve(analysis.scope, claim)
    with monkeypatch.context() as change:
        change.setattr(AnalysisDataRequirementRouteReader, 'read_unknown_historical',
            lambda self, scope, frozen: replace(original_read(self, scope, frozen),
                occurrence_id='00000000-0000-0000-0000-000000000000'))
        with pytest.raises(UnknownSourceGroupFrozen, match='ORIGINAL_SOURCE_GROUP_LINEAGE_DRIFT'):
            evidence_reader.resolve(analysis.scope, claim)
    with pytest.raises(ValueError):
        UnknownSourceGroupEvidenceReader(
            claims=analysis.source.reader._journal._claims, connect_factory=reader,
        ).resolve(analysis.scope, replace(claim, attempt=claim.attempt + 1))
    with pytest.raises(ValueError):
        UnknownSourceGroupEvidenceReader(
            claims=analysis.source.reader._journal._claims, connect_factory=reader,
        ).resolve(TenantScope(org_id='dev-org', project_id='dev-project'), claim)
    with pytest.raises(ValueError, match='READ_ONLY_TENANT_BOUNDARY_REQUIRED'):
        UnknownSourceGroupEvidenceReader(
            claims=analysis.source.reader._journal._claims, connect_factory=writer,
        ).resolve(analysis.scope, claim)
    assert state['calls'] == 1

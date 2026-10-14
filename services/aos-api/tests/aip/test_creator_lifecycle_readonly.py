"""Dedicated read-only snapshot tests; fixture rows are not human approvals."""
import copy
import json
from contextlib import contextmanager
from datetime import timedelta

import psycopg
import pytest
from psycopg import IsolationLevel

from aos_api.ecommerce_workshop_creator_lifecycle import CreatorActionLaneBinding
from aos_api.ecommerce_workshop_creator_lifecycle_readonly import (
    CreatorLifecycleReadonlyReader, CreatorLifecycleReadonlyError,
    MAX_ROWS, MAX_ITEM_BYTES, MAX_TOTAL_BYTES,
)
from test_creator_lifecycle_read_tenant import SCOPE, NOW, HASH, item, ref

TABLES = {
    'start': 'ecommerce_creator_batch_start_decision_revision',
    'lane': 'ecommerce_creator_lane_observation',
    'contract': 'ecommerce_creator_contract_revision',
    'delivery': 'ecommerce_creator_delivery_observation',
    'relationship': 'ecommerce_creator_relationship_revision',
}
METHODS = {
    'start': 'latest_start_for_tenant_or_none', 'lane': 'list_lane_observations',
    'contract': 'list_contracts', 'delivery': 'list_deliveries', 'relationship': 'list_relationships',
}


def row(kind, value=None):
    value = value or item(METHODS[kind])
    data = value.model_dump(mode='json', by_alias=True)
    identities = {'start': 'decisionId', 'lane': 'observationId', 'contract': 'collaborationId',
                  'delivery': 'observationId', 'relationship': 'relationshipId'}
    result = dict(org_id=SCOPE.org_id, project_id=SCOPE.project_id,
                  entity_id=data[identities[kind]], revision=data.get('revision', 1),
                  content_hash=data['contentHash'], created_at=NOW,
                  authority_bytes=len(json.dumps(data).encode()), authority_data=data)
    if kind == 'lane':
        result['decision_id'] = data['startDecisionRef']['resourceId']
    return result


def snapshot(rows=None, *, fail=None, readonly=True, isolation=IsolationLevel.REPEATABLE_READ, cutoff=NOW):
    rows = rows or {}
    calls, connections = [], []
    class Result:
        def __init__(self, values): self.values = values
        def fetchone(self): return self.values[0] if self.values else None
        def fetchall(self): return self.values
    class Connection:
        read_only = readonly
        isolation_level = isolation
        autocommit = False
        def execute(self, sql, params=()):
            assert sql.startswith('SELECT ')
            calls.append((sql, params))
            if 'transaction_timestamp()' in sql:
                return Result([dict(cutoff=cutoff)])
            assert tuple(params[:2]) == SCOPE.key
            assert cutoff in params
            kind = next(k for k, table in TABLES.items() if f'FROM {table} ' in sql)
            assert 'LIMIT %s' in sql
            assert params[-1] == (1 if kind == 'start' else MAX_ROWS + 1)
            assert 'created_at<=%s' in sql
            assert 'observed_at' not in sql
            assert 'CASE WHEN octet_length' in sql
            if fail == kind: raise psycopg.OperationalError('fixture unavailable')
            return Result(rows.get(kind, []))
        def commit(self): pytest.fail('reader must not commit a mutation')
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        connections.append(scope)
        yield Connection()
    return CreatorLifecycleReadonlyReader(connect_factory=connect), calls, connections


def started_rows():
    start = item(METHODS['start'])
    lane = CreatorActionLaneBinding(
        candidateRef=ref('CreatorCandidateRevision'), actionKind='outreach-message',
        actionTypeRef={**ref('ActionTypeRevision'), 'resourceId': 'ecommerce.creator.outreach-message'},
        impactPreviewRef=ref('ImpactPreviewRevision'), adapterCapabilityRef=ref('AdapterCapabilityRevision'),
        accountBindingRef=ref('AccountBindingRevision'), budgetReservationRef=ref('ActionBudgetReservationRevision'),
        approvalPolicyRef=ref('ApprovalPolicyRevision'), laneId='fixture-lane', bindingHash=HASH)
    start = start.model_copy(update={'lanes': [lane], 'ledger': start.ledger.model_copy(update={
        'eligible_items': 1, 'lanes': 1, 'prepared': 1})})
    observation = item(METHODS['lane']).model_copy(update={
        'start_decision_ref': type(lane.candidate_ref)(**dict(
            resourceType='CreatorBatchStartDecisionRevision', resourceId=start.decision_id,
            revision=start.revision, contentHash=start.content_hash))})
    return dict(start=[row('start', start)], lane=[row('lane', observation)])


def test_empty_is_complete_single_readonly_snapshot_with_database_cutoff():
    reader, calls, connections = snapshot()
    view = reader.read(SCOPE)
    assert len(connections) == 1 and len(calls) == 5
    assert view.evaluated_at == NOW and view.latest_start is None
    assert view.contracts == view.deliveries == view.relationships == []
    assert view.ledger.lanes == 0 and view.allowed_commands == []
    assert view.external_effects_allowed is False
    assert view.blockers == ['CREATOR_BATCH_START_NOT_AVAILABLE']


def test_complete_typed_view_and_lane_projection_without_producer_calls():
    rows = started_rows()
    rows.update({k: [row(k)] for k in ['contract', 'delivery', 'relationship']})
    reader, calls, connections = snapshot(rows)
    view = reader.read(SCOPE)
    assert len(connections) == 1 and len(calls) == 6
    assert view.latest_start.lanes[0].lane_id == 'fixture-lane'
    assert view.ledger.lanes == view.ledger.prepared == 1
    assert len(view.contracts) == len(view.deliveries) == len(view.relationships) == 1
    assert view.allowed_commands == [] and view.external_effects_allowed is False


@pytest.mark.parametrize('field,value', [
    ('org_id', 'dev-org'), ('project_id', 'other'), ('entity_id', 'wrong'),
    ('revision', 9), ('content_hash', 'b' * 64), ('created_at', NOW + timedelta(seconds=1)),
])
def test_outer_row_integrity_drift_is_rejected(field, value):
    bad = row('contract'); bad[field] = value
    reader, _, _ = snapshot(dict(contract=[bad]))
    with pytest.raises(CreatorLifecycleReadonlyError, match='AUTHORITY_DRIFT'):
        reader.read(SCOPE)


@pytest.mark.parametrize('field,value', [('orgId', 'dev-org'), ('projectId', 'other')])
def test_inner_json_tenant_drift_is_rejected(field, value):
    bad = row('contract'); bad['authority_data']['tenant'][field] = value
    reader, _, _ = snapshot(dict(contract=[bad]))
    with pytest.raises(CreatorLifecycleReadonlyError, match='AUTHORITY_DRIFT'):
        reader.read(SCOPE)


@pytest.mark.parametrize('readonly,isolation', [(False, IsolationLevel.REPEATABLE_READ),
                                               (True, IsolationLevel.READ_COMMITTED)])
def test_non_readonly_or_non_repeatable_connection_is_denied(readonly, isolation):
    reader, calls, _ = snapshot(readonly=readonly, isolation=isolation)
    with pytest.raises(CreatorLifecycleReadonlyError, match='CONNECTION_INVALID'):
        reader.read(SCOPE)
    assert calls == []


def test_database_failure_is_unavailable_not_empty_success():
    reader, _, _ = snapshot(fail='contract')
    with pytest.raises(CreatorLifecycleReadonlyError, match='UNAVAILABLE'):
        reader.read(SCOPE)


def test_clock_without_timezone_is_denied():
    reader, _, _ = snapshot(cutoff=NOW.replace(tzinfo=None))
    with pytest.raises(CreatorLifecycleReadonlyError, match='AUTHORITY_DRIFT'):
        reader.read(SCOPE)


def test_row_limit_sentinel_rejects_instead_of_truncating():
    reader, _, _ = snapshot(dict(contract=[row('contract')] * (MAX_ROWS + 1)))
    with pytest.raises(CreatorLifecycleReadonlyError, match='LIMIT_EXCEEDED'):
        reader.read(SCOPE)


def test_exact_row_limit_can_be_read_when_total_bytes_fit():
    reader, _, _ = snapshot(dict(contract=[row('contract')] * MAX_ROWS))
    assert len(reader.read(SCOPE).contracts) == MAX_ROWS


def test_sql_suppressed_large_json_is_rejected_before_parse():
    bad = row('contract'); bad.update(authority_bytes=MAX_ITEM_BYTES + 1, authority_data=None)
    reader, _, _ = snapshot(dict(contract=[bad]))
    with pytest.raises(CreatorLifecycleReadonlyError, match='LIMIT_EXCEEDED'):
        reader.read(SCOPE)


def test_total_byte_limit_is_not_treated_as_partial_or_empty():
    rows = [row('contract') for _ in range(MAX_TOTAL_BYTES // MAX_ITEM_BYTES + 1)]
    for value in rows: value['authority_bytes'] = MAX_ITEM_BYTES
    reader, _, _ = snapshot(dict(contract=rows))
    with pytest.raises(CreatorLifecycleReadonlyError, match='LIMIT_EXCEEDED'):
        reader.read(SCOPE)


@pytest.mark.parametrize('mutation', ['decision', 'hash', 'lane'])
def test_lane_exact_lineage_drift_is_rejected(mutation):
    rows = copy.deepcopy(started_rows()); bad = rows['lane'][0]
    if mutation == 'decision': bad['decision_id'] = 'other'
    if mutation == 'hash': bad['authority_data']['startDecisionRef']['contentHash'] = 'b' * 64
    if mutation == 'lane': bad['authority_data']['laneId'] = 'other'
    reader, _, _ = snapshot(rows)
    with pytest.raises(CreatorLifecycleReadonlyError, match='AUTHORITY_DRIFT'):
        reader.read(SCOPE)


def test_bad_json_shape_fails_closed():
    bad = row('contract'); bad['authority_data'] = {'tenant': {'orgId': 'org-org'}}
    reader, _, _ = snapshot(dict(contract=[bad]))
    with pytest.raises(CreatorLifecycleReadonlyError, match='AUTHORITY_DRIFT'):
        reader.read(SCOPE)


def test_delivery_observation_without_dto_revision_requires_stored_v1():
    bad = row('delivery'); bad['revision'] = 2
    reader, _, _ = snapshot(dict(delivery=[bad]))
    with pytest.raises(CreatorLifecycleReadonlyError, match='AUTHORITY_DRIFT'):
        reader.read(SCOPE)

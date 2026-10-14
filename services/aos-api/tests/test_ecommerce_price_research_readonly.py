"""Saved price facts must prove original hashes, not just parse a DTO."""
from copy import deepcopy
from datetime import timedelta
import importlib.util
from pathlib import Path

import psycopg
from psycopg import IsolationLevel
import pytest

from aos_api.ecommerce_price_research_readonly import (
    PriceResearchReadonlyError, PriceResearchReadonlyReader, MAX_ROW_BYTES,
)


@pytest.fixture
def saved():
    path = Path(__file__).parent / 'aip/test_w6_05_price_research.py'
    spec = importlib.util.spec_from_file_location('original_price_test_fixture', path)
    fx = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fx)
    fx.SCOPE = fx.TenantScope('dev-org', 'fixture-project')
    instances = []
    original = fx.Store

    class CaptureStore(original):
        def __init__(self):
            super().__init__()
            instances.append(self)

    fx.Store = CaptureStore
    # Uses the unchanged original producer and original existing test assertions.
    fx.test_full_prepare_freeze_conserves_items_and_has_zero_side_effects()
    prepared, frozen = instances[0].batches['price-batch-1']

    def row(item):
        return dict(org_id=fx.SCOPE.org_id, project_id=fx.SCOPE.project_id,
                    batch_id=item.batch_id, revision=item.revision,
                    content_hash=item.content_hash, created_at=item.created_at,
                    payload_bytes=4096, authority_data=item.model_dump(mode='json', by_alias=True))

    return fx, row(prepared), row(frozen)


class Result:
    def __init__(self, value): self.value = value
    def fetchone(self): return self.value


class Connection:
    read_only = True
    autocommit = False
    isolation_level = IsolationLevel.REPEATABLE_READ

    def __init__(self, cutoff, latest, prior=None):
        self.cutoff, self.latest, self.prior = cutoff, latest, prior
        self.sql = []
        self.entered = 0
        self.fail = False

    def __enter__(self): self.entered += 1; return self
    def __exit__(self, *args): return False

    def execute(self, sql, params=None):
        self.sql.append((sql, params))
        assert sql.lstrip().upper().startswith('SELECT')
        assert 'INSERT' not in sql.upper() and 'UPDATE' not in sql.upper()
        if self.fail: raise psycopg.OperationalError('private backend detail')
        if 'transaction_timestamp' in sql: return Result({'cutoff': self.cutoff})
        assert 'ecommerce_price_research_batch_revision' in sql
        assert 'CASE WHEN' in sql and 'octet_length' in sql and 'LIMIT 1' in sql
        assert 'created_at<=' not in sql.replace(' ', '').lower()
        assert params[:2] == ('dev-org', 'fixture-project')
        return Result(self.prior if len(params) > 2 else self.latest)


def read(saved, latest, prior=None, configure=None):
    fx = saved[0]
    conn = Connection(fx.NOW + timedelta(days=1), latest, prior)
    if configure: configure(conn)
    reader = PriceResearchReadonlyReader(connect_factory=lambda scope: conn)
    result = reader.read(fx.SCOPE)
    assert conn.entered == 1
    return result, conn


def test_verified_empty_is_not_authority_unavailable(saved):
    view, conn = read(saved, None)
    assert view.latest_batch is None
    assert view.blockers == ['PRICE_RESEARCH_BATCH_NOT_AVAILABLE']
    assert view.allowed_commands == [] and view.external_effects_allowed is False
    assert view.evaluated_at == saved[0].NOW + timedelta(days=1)
    assert len(conn.sql) == 2


@pytest.mark.parametrize('frozen', [False, True])
def test_original_nonempty_producer_is_readable_without_operating_authority(saved, frozen):
    _, prepared, final = saved
    chosen = final if frozen else prepared
    view, conn = read(saved, chosen, prepared if frozen else None)
    assert view.latest_batch.model_dump(mode='json', by_alias=True) == chosen['authority_data']
    assert view.latest_batch.ledger.input == view.latest_batch.ledger.eligible == 1
    assert view.allowed_commands == [] and view.external_effects_allowed is False
    assert view.primary_colleague == '数据参谋'
    assert len(conn.sql) == (3 if frozen else 2)


@pytest.mark.parametrize('mutation', [
    'outer_tenant', 'nested_tenant', 'outer_id', 'outer_revision', 'raw_revision_bool',
    'version', 'outer_hash', 'payload_hash', 'future', 'outer_time', 'naive_time',
    'item_hash', 'item_count', 'ledger_counts', 'extra_ref', 'missing_ref',
    'ref_kind', 'ref_revision_bool', 'skill_order', 'logic_identity', 'duplicate_target',
    'side_effect', 'boolean_gate', 'private_actor', 'private_reason', 'payload_size',
    'stale_unproved', 'prepared_prior', 'missing_zero_count',
])
def test_corrupt_saved_facts_are_not_success_or_empty(saved, mutation):
    row = deepcopy(saved[1]); raw = row['authority_data']
    if mutation == 'outer_tenant': row['org_id'] = 'foreign'
    elif mutation == 'nested_tenant': raw['tenant']['projectId'] = 'foreign'
    elif mutation == 'outer_id': row['batch_id'] = 'other'
    elif mutation == 'outer_revision': row['revision'] = 2
    elif mutation == 'raw_revision_bool': raw['revision'] = True
    elif mutation == 'version': raw['version'] = 3
    elif mutation == 'outer_hash': row['content_hash'] = 'f' * 64
    elif mutation == 'payload_hash': raw['contentHash'] = row['content_hash'] = 'f' * 64
    elif mutation == 'future':
        row['created_at'] = saved[0].NOW + timedelta(days=2)
        raw['createdAt'] = row['created_at'].isoformat()
    elif mutation == 'outer_time': row['created_at'] += timedelta(seconds=1)
    elif mutation == 'naive_time': raw['createdAt'] = saved[0].NOW.replace(tzinfo=None).isoformat()
    elif mutation == 'item_hash': raw['itemHashes'][0] = 'f' * 64
    elif mutation == 'item_count': raw['itemHashes'] = []
    elif mutation == 'ledger_counts': raw['ledger'].update(eligible=0, excluded=1)
    elif mutation == 'extra_ref': raw['exactRefs']['unexpected'] = raw['exactRefs']['brief']
    elif mutation == 'missing_ref': del raw['exactRefs']['budgetSnapshot']
    elif mutation == 'ref_kind': raw['exactRefs']['budgetSnapshot']['resourceType'] = 'Approval'
    elif mutation == 'ref_revision_bool': raw['exactRefs']['brief']['revision'] = True
    elif mutation == 'skill_order': raw['skillRefs'].reverse()
    elif mutation == 'logic_identity': raw['exactRefs']['logic']['resourceId'] = 'other'
    elif mutation == 'duplicate_target':
        raw['items'] *= 2; raw['itemHashes'] *= 2; raw['ledger'].update(input=2, eligible=2)
    elif mutation == 'side_effect': raw['providerCallCount'] = 1
    elif mutation == 'boolean_gate': raw['items'][0]['budgetEligible'] = 1
    elif mutation == 'private_actor': raw['createdBy'] = 'private@example.com'
    elif mutation == 'private_reason': raw['items'][0]['reasonCodes'] = ['private@example.com']
    elif mutation == 'payload_size': row.update(payload_bytes=MAX_ROW_BYTES + 1, authority_data=None)
    elif mutation == 'stale_unproved': raw['lifecycle'] = 'stale'
    elif mutation == 'prepared_prior': raw['priorContentHash'] = 'f' * 64
    elif mutation == 'missing_zero_count': del raw['providerCallCount']
    with pytest.raises(PriceResearchReadonlyError): read(saved, row)


@pytest.mark.parametrize('mutation', ['items', 'ledger', 'refs', 'missing_prior', 'prior_hash', 'prior_identity', 'time', 'version'])
def test_frozen_short_hash_cannot_mask_changed_inherited_facts(saved, mutation):
    prior, row = deepcopy(saved[1]), deepcopy(saved[2])
    raw = row['authority_data']
    if mutation == 'items': raw['items'][0]['reasonCodes'] = ['changed-after-prepare']
    elif mutation == 'ledger': raw['ledger'].update(eligible=0, excluded=1)
    elif mutation == 'refs': raw['skillRefs'][0]['receiptId'] = 'different'
    elif mutation == 'missing_prior': prior = None
    elif mutation == 'prior_hash': prior['content_hash'] = 'f' * 64
    elif mutation == 'prior_identity': prior['batch_id'] = 'other'
    elif mutation == 'time':
        row['created_at'] -= timedelta(seconds=1); raw['createdAt'] = row['created_at'].isoformat()
    elif mutation == 'version': raw['version'] = 3
    # In particular the items/ledger/skills edits do not alter the producer's short hash.
    assert raw['contentHash'] == saved[2]['authority_data']['contentHash']
    with pytest.raises(PriceResearchReadonlyError): read(saved, row, prior)


@pytest.mark.parametrize('field,value', [('read_only', False), ('autocommit', True), ('isolation_level', IsolationLevel.READ_COMMITTED)])
def test_unknown_connection_does_not_read(saved, field, value):
    with pytest.raises(PriceResearchReadonlyError):
        read(saved, None, configure=lambda conn: setattr(conn, field, value))


def test_sql_failure_is_safe_failure_not_verified_empty(saved):
    with pytest.raises(PriceResearchReadonlyError) as caught:
        read(saved, None, configure=lambda conn: setattr(conn, 'fail', True))
    assert caught.value.code == 'PRICE_RESEARCH_READ_UNAVAILABLE'
    assert 'private' not in str(caught.value)

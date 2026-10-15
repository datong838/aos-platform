"""Saved customer facts, not contact/consent admission; synthetic producer fixtures."""
from copy import deepcopy
from datetime import timedelta
import importlib.util
import json
from pathlib import Path

import psycopg
from psycopg import IsolationLevel
import pytest

from aos_api import ecommerce_customer_lifecycle_readonly as reader


def producer_fixture(frozen=True):
    spec = importlib.util.spec_from_file_location('customer_read_fixture', Path(__file__).parent / 'aip/test_w6_07_customer_lifecycle.py')
    f = importlib.util.module_from_spec(spec); spec.loader.exec_module(f)
    f.SCOPE = f.TenantScope('dev-org', 'fixture-project')
    def exact(item, kind, identity):
        name = getattr(item, identity)
        return f.CustomerExactRef(resourceType=kind, resourceId=name, revision=item.revision,
                                 contentHash='sha256:' + item.content_hash, receiptId='receipt-' + name)
    f.exact = exact
    store, service, *refs = f.authority_fixture()
    batch = service.prepare_batch(f.SCOPE, f.batch_request(*refs), 'synthetic-operator', now=f.NOW)
    if frozen:
        names = {'segment': 'segment_ref', 'journey': 'journey_ref', 'dialogue': 'dialogue_ref',
                 'consentPolicy': 'consent_policy_ref', 'frequencyPolicy': 'frequency_policy_ref', 'channelCapability': 'channel_capability_ref'}
        service.freeze_batch(f.SCOPE, batch.batch_id, f.FreezeCustomerDialogueBatchRequest(
            expectedVersion=1, expectedContentHash=batch.content_hash,
            exactRefs={k: getattr(batch, v) for k, v in names.items()}, itemHashes=batch.item_hashes),
            'synthetic-reviewer', now=f.NOW + timedelta(seconds=1))
    data = {}
    for table, identity, _model, _request, name in reader.POLICIES:
        attr = {'consent_policy': 'policies', 'segment': 'segments', 'journey': 'journeys', 'dialogue': 'dialogues'}[name]
        data[table] = [row(item, identity) for item in getattr(store, attr).values()]
    data[reader.BATCH_TABLE] = [row(item, 'batch_id') for item in store.batches[batch.batch_id]]
    return f, data


def row(item, identity):
    raw = item.model_dump(mode='json', by_alias=True)
    return dict(org_id=item.tenant.org_id, project_id=item.tenant.project_id,
                identity=getattr(item, identity), revision=item.revision, content_hash=item.content_hash,
                created_at=item.created_at, size=len(json.dumps(raw).encode()), authority_data=raw)


class Result:
    def __init__(self, value): self.value = value
    def fetchone(self): return self.value


class Connection:
    read_only = True
    autocommit = False
    isolation_level = IsolationLevel.REPEATABLE_READ
    def __init__(self, data, cutoff):
        self.data, self.cutoff, self.calls, self.overrides = deepcopy(data), cutoff, [], {}
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        if sql.startswith('SET LOCAL'): return Result(None)
        if 'transaction_timestamp()' in sql: return Result({'cutoff': self.cutoff})
        table = next(t for t in self.data if 'FROM ' + t + ' ' in sql)
        rows = self.data[table]
        if 'COUNT(*)' in sql:
            assert params == ('dev-org', 'fixture-project') and 'LIMIT' not in sql
            return Result(self.overrides.get(table, dict(count=len(rows), invalid_count=0,
                          latest_created_at=max((r['created_at'] for r in rows), default=None))))
        assert 'LIMIT 1' in sql and 'CASE WHEN octet_length' in sql
        assert params[:2] == ('dev-org', 'fixture-project')
        if len(params) > 2: rows = [r for r in rows if (r['identity'], r['revision']) == tuple(params[2:])]
        return Result(deepcopy(max(rows, key=lambda r: (r['created_at'], r['revision'], r['identity']))) if rows else None)


def run(data=None, frozen=True):
    f, original = producer_fixture(frozen)
    conn = Connection(original if data is None else data, f.NOW + timedelta(seconds=2))
    return f, conn, reader.CustomerLifecycleReadonlyReader(connect_factory=lambda scope: conn)


@pytest.mark.parametrize('frozen', [False, True])
def test_original_typed_producer_hashes_and_unknown_remain(frozen):
    f, conn, subject = run(frozen=frozen)
    view = subject.read(f.SCOPE)
    assert view.tenant.org_id == 'dev-org' and view.primary_colleague == '私域管家'
    assert view.consent_policy_count == view.segment_count == view.journey_count == view.dialogue_count == 1
    assert view.latest_batch.lifecycle == ('frozen' if frozen else 'prepared')
    assert view.latest_batch.ledger.eligible == view.latest_batch.ledger.unknown == 1
    unknown = view.latest_batch.items[1]
    assert unknown.consent_decision.value == 'unknown' and unknown.retention_active is unknown.k_anonymity_satisfied is None
    assert view.allowed_commands == []
    assert not any((view.contact_resolution_allowed, view.start_allowed, view.send_allowed, view.external_effects_allowed))
    assert len([s for s, _ in conn.calls if 'COUNT(*)' in s]) == 4


def test_real_empty_and_complete_saved_revision_count():
    f, conn, subject = run()
    for table in conn.data: conn.data[table] = []
    conn.overrides[reader.POLICIES[0][0]] = dict(count=9000, invalid_count=0, latest_created_at=f.NOW)
    view = subject.read(f.SCOPE)
    assert view.consent_policy_count == 9000 and view.segment_count == 0 and view.latest_batch is None


@pytest.mark.parametrize('field,value', [('count', True), ('count', -1), ('count', 2**53), ('invalid_count', 1), ('invalid_count', False)])
def test_invalid_aggregate_is_never_empty_success(field, value):
    f, conn, subject = run()
    entry = dict(count=1, invalid_count=0, latest_created_at=f.NOW); entry[field] = value
    conn.overrides[reader.POLICIES[0][0]] = entry
    with pytest.raises(reader.CustomerLifecycleReadonlyError): subject.read(f.SCOPE)


@pytest.mark.parametrize('attribute,value', [('read_only', False), ('autocommit', True), ('isolation_level', IsolationLevel.READ_COMMITTED)])
def test_snapshot_contract_required(attribute, value):
    f, conn, subject = run(); setattr(conn, attribute, value)
    with pytest.raises(reader.CustomerLifecycleReadonlyError): subject.read(f.SCOPE)


@pytest.mark.parametrize('mutation', ['tenant', 'hash', 'itemHash', 'bindingHash', 'prior', 'inherited', 'unknown', 'bool', 'missing', 'extra', 'privacy', 'oversize', 'time', 'stale', 'policyHash', 'lineage'])
def test_saved_tampering_rejected(mutation):
    f, conn, subject = run(); latest = conn.data[reader.BATCH_TABLE][-1]; raw = latest['authority_data']
    if mutation == 'tenant': raw['tenant']['orgId'] = 'foreign'
    elif mutation == 'hash': raw['contentHash'] = 'a' * 64
    elif mutation == 'itemHash': raw['itemHashes'][0] = 'b' * 64
    elif mutation == 'bindingHash': raw['bindingHash'] = 'c' * 64
    elif mutation == 'prior': raw['priorContentHash'] = 'd' * 64
    elif mutation == 'inherited': raw['items'][0]['itemKey'] = 'changed'
    elif mutation == 'unknown': raw['items'][1]['disposition'] = 'eligible'
    elif mutation == 'bool': raw['sendCount'] = False
    elif mutation == 'missing': del raw['actionCount']
    elif mutation == 'extra': raw['mobile'] = 'fixture-private-value'
    elif mutation == 'privacy': raw['createdBy'] = 'fixture@example.test'
    elif mutation == 'oversize': latest['size'] = reader.MAX_ROW_BYTES + 1; latest['authority_data'] = None
    elif mutation == 'time': latest['created_at'] = conn.cutoff + timedelta(seconds=1)
    elif mutation == 'stale': raw['lifecycle'] = 'stale'
    elif mutation == 'policyHash': conn.data[reader.POLICIES[0][0]][0]['authority_data']['purpose'] = 'changed'
    elif mutation == 'lineage': conn.data[reader.POLICIES[1][0]][0]['authority_data']['consentPolicyRef']['resourceId'] = 'different'
    with pytest.raises(reader.CustomerLifecycleReadonlyError): subject.read(f.SCOPE)


def test_future_aggregate_not_hidden_by_cutoff_filter():
    f, conn, subject = run()
    conn.overrides[reader.POLICIES[0][0]] = dict(count=1, invalid_count=0, latest_created_at=conn.cutoff + timedelta(seconds=1))
    with pytest.raises(reader.CustomerLifecycleReadonlyError): subject.read(f.SCOPE)


def test_database_failure_is_stable_not_fake_zero():
    f, conn, subject = run()
    def fail(*args): raise psycopg.OperationalError('private database details')
    conn.execute = fail
    with pytest.raises(reader.CustomerLifecycleReadonlyError, match='CUSTOMER_LIFECYCLE_READ_AUTHORITY_UNAVAILABLE'): subject.read(f.SCOPE)


def test_time_budget_checked_between_queries(monkeypatch):
    f, conn, subject = run(); ticks = iter([0, 11])
    monkeypatch.setattr(reader, 'monotonic', lambda: next(ticks))
    with pytest.raises(reader.CustomerLifecycleReadonlyError, match='LIMIT_EXCEEDED'): subject.read(f.SCOPE)

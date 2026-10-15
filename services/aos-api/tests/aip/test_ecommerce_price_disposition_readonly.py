"""Installed read compatibility and failure isolation; no real DB in this file."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import timedelta
import importlib.util
from pathlib import Path

import pytest


def original():
    path = Path(__file__).with_name('test_w6_06_price_disposition.py')
    spec = importlib.util.spec_from_file_location('disposition_read_fixture', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def saved_rows(*, scope=None, at=None):
    f = original()
    if scope is not None: f.SCOPE = scope
    if at is not None: f.NOW = at
    store, service, case, sku = f.authority_fixture()
    frozen_rows = []
    for kind in f.PriceDispositionKind:
        contract = f.create_contract(service, kind)
        # Original producer fixture uses an approximate ref helper; this experiment uses exact hashes.
        exact = lambda obj, typ, field: f.PriceExactRef(resourceType=typ, resourceId=getattr(obj, field),
            revision=obj.revision, contentHash='sha256:' + obj.content_hash, receiptId='receipt-' + getattr(obj, field))
        request = f.PreparePriceDispositionRequest(dispositionId='read-' + kind.value,
            caseRef=exact(case, 'PriceCaseRevision', 'case_id'),
            contractRef=exact(contract, 'PriceDispositionContractRevision', 'contract_id'), targetRefs=[sku],
            gateRefs={key: f.ref(typ, key) for key, typ in f.REQUIRED_GATE_TYPES[kind].items()},
            purpose='read compatibility', requestedOutcome='review only')
        prepared = service.prepare(f.SCOPE, request, 'synthetic', now=f.NOW)
        frozen = service.freeze(f.SCOPE, prepared.disposition_id, f.FreezePriceDispositionRequest(
            expectedVersion=1, expectedContentHash=prepared.content_hash,
            exactRefs={'case': prepared.case_ref, 'contract': prepared.contract_ref, **prepared.gate_refs}), 'reviewer', now=f.NOW)
        frozen_rows.append(frozen)
    earlier = frozen_rows[0]
    receipt = f.ref('AdoptionReceipt', 'read-adoption')
    store.receipts[(*f.SCOPE.key, receipt.resource_id)] = (receipt.content_hash, earlier.binding_hash)
    service.record_observation(f.SCOPE, f.RecordPriceDispositionObservationRequest(
        dispositionRef=exact(earlier, 'PriceDispositionRevision', 'disposition_id'), receiptRef=receipt,
        outcome='adopted', observedAt=f.NOW))
    collections = {
        'ecommerce_price_case_revision': (list(store.cases.values()), 'case_id'),
        'ecommerce_price_disposition_contract_revision': (list(store.contracts.values()), 'contract_id'),
        'ecommerce_price_disposition_revision': ([r for revisions in store.dispositions.values() for r in revisions], 'disposition_id'),
        'ecommerce_price_disposition_observation': (store.observations, 'observation_id'),
    }
    tables = {}
    for table, (items, identity) in collections.items():
        tables[table] = [{'org_id': f.SCOPE.org_id, 'project_id': f.SCOPE.project_id,
            'identity': getattr(row, identity), 'revision': row.revision, 'content_hash': row.content_hash,
            'created_at': getattr(row, 'created_at', getattr(row, 'observed_at', f.NOW)),
            'size': len(row.model_dump_json(by_alias=True).encode()),
            'authority_data': row.model_dump(mode='json', by_alias=True)} for row in items]
        tables[table].sort(key=lambda row: (row['created_at'], row['revision'], row['identity']))
    return f, tables


class Cursor:
    def __init__(self, rows): self.rows = rows
    def fetchall(self): return deepcopy(self.rows)
    def fetchone(self): return deepcopy(self.rows[0])


class Connection:
    read_only = True
    autocommit = False
    from psycopg import IsolationLevel
    isolation_level = IsolationLevel.REPEATABLE_READ
    def __init__(self, tables, cutoff): self.tables = tables; self.cutoff = cutoff; self.calls = []; self.payload_calls = 0
    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        if sql.startswith('SET LOCAL'): return Cursor([])
        if 'transaction_timestamp()' in sql: return Cursor([{'cutoff': self.cutoff}])
        table = next(table for table in self.tables if 'FROM ' + table + ' ' in sql)
        assert params == ('org-org', 'dev-project')
        assert 'LIMIT 513' in sql and 'ORDER BY created_at,revision,' in sql
        rows = deepcopy(self.tables[table])
        if 'THEN authority_data' in sql:
            self.payload_calls += 1
        else:
            for row in rows: row.pop('authority_data')
        return Cursor(rows[:513])


def reader_for(tables, f):
    from aos_api.ecommerce_price_disposition_readonly import EcommercePriceDispositionReadonlyReader
    conn = Connection(tables, f.NOW + timedelta(days=1))
    opened = []
    @contextmanager
    def connect(scope):
        assert scope == f.SCOPE
        opened.append(scope)
        yield conn
    return EcommercePriceDispositionReadonlyReader(connect_factory=connect), conn, opened


def test_original_producer_complete_counts_and_earlier_observation_single_snapshot():
    f, tables = saved_rows(); reader, conn, opened = reader_for(tables, f)
    view = reader.read(f.SCOPE)
    assert len(opened) == 1 and conn.payload_calls == 4
    assert view.case_count == 1 and sum(view.disposition_counts.values()) == 8
    assert set(view.disposition_counts.values()) == {2}
    assert view.latest_observation.disposition_ref.resource_id != view.latest_disposition.disposition_id
    assert view.allowed_commands == [] and view.external_effects_allowed is view.repricing_enabled is False


def test_true_empty_snapshot_is_zero_without_commands():
    f, tables = saved_rows()
    for table in tables: tables[table] = []
    reader, _, _ = reader_for(tables, f); view = reader.read(f.SCOPE)
    assert view.case_count == 0 and sum(view.disposition_counts.values()) == 0
    assert view.latest_disposition is view.latest_observation is None
    assert view.allowed_commands == []


@pytest.mark.parametrize('change', ['tenant', 'outer_hash', 'outer_id', 'future', 'typed_bool', 'missing_field',
    'binding', 'frozen_inheritance', 'observation_hash', 'observation_link', 'privacy', 'case_lifecycle'])
def test_corrupt_selected_rows_fail_closed(change):
    from aos_api.ecommerce_price_disposition_readonly import PriceDispositionReadonlyError
    f, tables = saved_rows()
    case = tables['ecommerce_price_case_revision'][0]
    disposition = tables['ecommerce_price_disposition_revision'][0]
    observation = tables['ecommerce_price_disposition_observation'][0]
    if change == 'tenant': case['authority_data']['tenant']['orgId'] = 'foreign'
    elif change == 'outer_hash': case['content_hash'] = '0' * 64
    elif change == 'outer_id': case['identity'] = 'drifted'
    elif change == 'future': case['created_at'] = f.NOW + timedelta(days=2)
    elif change == 'typed_bool': disposition['authority_data']['executionAllowed'] = 0
    elif change == 'missing_field': del disposition['authority_data']['providerCallCount']
    elif change == 'binding': disposition['authority_data']['bindingHash'] = '0' * 64
    elif change == 'frozen_inheritance': tables['ecommerce_price_disposition_revision'][-1]['authority_data']['purpose'] = 'changed'
    elif change == 'observation_hash': observation['authority_data']['contentHash'] = '0' * 64
    elif change == 'observation_link': observation['authority_data']['dispositionRef']['contentHash'] = 'sha256:' + '0' * 64
    elif change == 'privacy': case['authority_data']['createdBy'] = 'person@example.com'
    elif change == 'case_lifecycle': case['authority_data']['lifecycle'] = 'closed'
    reader, _, _ = reader_for(tables, f)
    with pytest.raises(PriceDispositionReadonlyError): reader.read(f.SCOPE)


@pytest.mark.parametrize('limit', ['rows', 'row_bytes', 'total_bytes'])
def test_metadata_limits_reject_before_any_payload_transfer(limit):
    from aos_api.ecommerce_price_disposition_readonly import PriceDispositionReadonlyError
    f, tables = saved_rows()
    case = tables['ecommerce_price_case_revision'][0]
    if limit == 'rows': tables['ecommerce_price_case_revision'] = [deepcopy(case) for _ in range(513)]
    elif limit == 'row_bytes': case['size'] = 1024 * 1024 + 1
    else:
        for rows in tables.values():
            for row in rows: row['size'] = 1024 * 1024
    reader, conn, _ = reader_for(tables, f)
    with pytest.raises(PriceDispositionReadonlyError, match='LIMIT_EXCEEDED'): reader.read(f.SCOPE)
    assert conn.payload_calls == 0


def test_database_failure_does_not_fabricate_empty_counts_or_leak_message():
    import psycopg
    from aos_api.ecommerce_price_disposition_readonly import EcommercePriceDispositionReadonlyReader, PriceDispositionReadonlyError
    f = original()
    @contextmanager
    def failed(_scope):
        raise psycopg.OperationalError('private connection text')
        yield
    with pytest.raises(PriceDispositionReadonlyError, match='AUTHORITY_UNAVAILABLE') as caught:
        EcommercePriceDispositionReadonlyReader(connect_factory=failed).read(f.SCOPE)
    assert 'private' not in str(caught.value)


@pytest.mark.parametrize('attribute,value', [('read_only', False), ('autocommit', True), ('isolation_level', None)])
def test_connection_characteristics_must_be_proven_before_select(attribute, value):
    from aos_api.ecommerce_price_disposition_readonly import PriceDispositionReadonlyError
    f, tables = saved_rows(); reader, conn, _ = reader_for(tables, f)
    setattr(conn, attribute, value)
    with pytest.raises(PriceDispositionReadonlyError, match='AUTHORITY_DRIFT'): reader.read(f.SCOPE)
    assert conn.calls == []

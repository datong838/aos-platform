"""Original W6-07/W6-08 synthetic facts; no operational consent or contact."""
from copy import deepcopy
from datetime import timedelta
import importlib.util
import json
from pathlib import Path

import psycopg
from psycopg import IsolationLevel
import pytest

from aos_api import ecommerce_customer_contact_readonly as reader
from aos_api import ecommerce_workshop_customer_contact as d


TABLES = {
    'policy': 'ecommerce_customer_consent_policy_revision',
    'segment': 'ecommerce_customer_segment_revision',
    'journey': 'ecommerce_customer_journey_revision',
    'dialogue': 'ecommerce_customer_dialogue_strategy_revision',
    'batch': 'ecommerce_customer_dialogue_batch_revision',
    'frequency': 'ecommerce_customer_frequency_policy_revision',
    'reservation': 'ecommerce_customer_frequency_reservation_revision',
    'withdrawal': 'ecommerce_customer_consent_withdrawal_observation',
    'start': 'ecommerce_customer_batch_start_decision_revision',
    'observation': 'ecommerce_customer_dispatch_observation',
}


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parent / path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def row(item, identity, date='created_at', **extra):
    raw = d.customer_start_authority_data(item) if isinstance(item, d.CustomerBatchStartDecisionRevision) else item.model_dump(mode='json', by_alias=True)
    return dict(org_id=item.tenant.org_id, project_id=item.tenant.project_id, identity=getattr(item, identity),
                revision=getattr(item, 'revision', 1), content_hash=item.content_hash, created_at=getattr(item, date),
                authority_data=raw, size=len(json.dumps(raw).encode()), **extra)


def producer_fixture(observation='unknown'):
    lf = _module('lifecycle_read_fixture', 'aip/test_w6_07_customer_lifecycle.py')
    cf = _module('contact_read_fixture', 'aip/test_w6_08_customer_contact.py')
    scope = lf.TenantScope('dev-org', 'fixture-project'); lf.SCOPE = cf.SCOPE = scope
    def exact(item, kind, identity):
        name = getattr(item, identity)
        return lf.CustomerExactRef(resourceType=kind, resourceId=name, revision=item.revision,
                                   contentHash='sha256:' + item.content_hash, receiptId='receipt-' + name)
    lf.exact = exact
    life_store, life, *refs = lf.authority_fixture(); store = cf.MemoryStore()
    class BatchStore:
        def latest_batch(self, tenant, identity):
            assert tenant == scope
            return life_store.latest_batch(tenant, identity)
    service = d.EcommerceWorkshopCustomerContactService(store, BatchStore())
    frequency = service.create_frequency_policy(scope, d.CreateCustomerFrequencyPolicyRequest(
        policyId='frequency', revision=1, channel='wecom', purpose='retention', timezone='Asia/Shanghai',
        quietHoursStart='22:00', quietHoursEnd='08:00', rollingWindowHours=168, maximumContacts=2), 'synthetic-operator', now=lf.NOW)
    request = lf.batch_request(*refs)
    third = request.items[0].model_copy(update={'item_key': 'item-3', 'customer_ref': lf.ref('CustomerLiteProjectionRevision', 'customer-3')})
    request = request.model_copy(update={'frequency_policy_ref': exact(frequency, 'FrequencyPolicyRevision', 'policy_id'), 'items': [*request.items, third]})
    prepared = life.prepare_batch(scope, request, 'synthetic-operator', now=lf.NOW)
    names = {'segment': 'segment_ref', 'journey': 'journey_ref', 'dialogue': 'dialogue_ref', 'consentPolicy': 'consent_policy_ref', 'frequencyPolicy': 'frequency_policy_ref', 'channelCapability': 'channel_capability_ref'}
    batch = life.freeze_batch(scope, prepared.batch_id, lf.FreezeCustomerDialogueBatchRequest(
        expectedVersion=1, expectedContentHash=prepared.content_hash, exactRefs={k: getattr(prepared, v) for k, v in names.items()}, itemHashes=prepared.item_hashes), 'synthetic-reviewer', now=lf.NOW + timedelta(seconds=1))
    service.record_withdrawal(scope, d.RecordCustomerConsentWithdrawalRequest(
        customerRef=third.customer_ref, consentPolicyRef=batch.consent_policy_ref, purpose='retention', channel='wecom', sequence=9, observedAt=lf.NOW + timedelta(seconds=1)))
    payload = cf.start_request(batch).model_dump(mode='json', by_alias=True)
    payload['items'] = [dict(itemKey=i.item_key, itemHash=batch.item_hashes[n], customerRef=i.customer_ref.model_dump(mode='json', by_alias=True)) for n, i in enumerate(batch.items) if i.disposition.value == 'eligible']
    start = service.start_batch(scope, batch.batch_id, d.StartCustomerDialogueBatchRequest.model_validate(payload), 'synthetic-operator', now=lf.NOW + timedelta(seconds=2))
    if observation:
        receipt = cf.ref('ActionReceipt', 'synthetic-receipt', 'f'); binding = start.items[0]
        store.receipts[(*scope.key, receipt.resource_id)] = (receipt.content_hash, binding.binding_hash)
        service.record_dispatch_observation(scope, d.RecordCustomerDispatchObservationRequest(
            startDecisionRef=exact(start, 'CustomerBatchStartDecisionRevision', 'decision_id'), itemKey=binding.item_key,
            actionReceiptRef=receipt, state=observation,
            resolvedState='applied' if observation == 'disputed' else None,
            manualCaseRef=cf.ref('ManualReconcileCase', 'synthetic-case') if observation == 'disputed' else None,
            observedAt=lf.NOW + timedelta(seconds=3)))
    data = {
        TABLES['policy']: [row(i, 'policy_id') for i in life_store.policies.values()],
        TABLES['segment']: [row(i, 'segment_id') for i in life_store.segments.values()],
        TABLES['journey']: [row(i, 'journey_id') for i in life_store.journeys.values()],
        TABLES['dialogue']: [row(i, 'dialogue_id') for i in life_store.dialogues.values()],
        TABLES['batch']: [row(i, 'batch_id') for i in life_store.batches[batch.batch_id]],
        TABLES['frequency']: [row(i, 'policy_id') for i in store.policies],
        TABLES['reservation']: [row(i, 'reservation_id', customer_id=i.customer_ref.resource_id, policy_id=i.frequency_policy_ref.resource_id, sequence=i.sequence, status=i.status) for i in store.reservations.values()],
        TABLES['withdrawal']: [row(i, 'observation_id', 'observed_at', customer_id=i.customer_ref.resource_id, consent_policy_id=i.consent_policy_ref.resource_id, sequence=i.sequence) for i in store.withdrawals],
        TABLES['start']: [row(start, 'decision_id', 'started_at', batch_id=start.batch_ref.resource_id)],
        TABLES['observation']: [row(i, 'observation_id', 'observed_at', decision_id=i.start_decision_ref.resource_id, item_key=i.item_key) for i in store.observations],
    }
    return scope, lf.NOW + timedelta(seconds=4), data, start


class Result:
    def __init__(self, value): self.value = value
    def fetchone(self): return deepcopy(self.value)
    def fetchall(self): return deepcopy(self.value)


class Connection:
    read_only = True
    autocommit = False
    isolation_level = IsolationLevel.REPEATABLE_READ
    def __init__(self, data, cutoff):
        self.data, self.cutoff, self.calls, self.overrides = deepcopy(data), cutoff, [], {}
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def execute(self, query, params=None):
        self.calls.append((query, params))
        if query.startswith('SET LOCAL'): return Result(None)
        if 'transaction_timestamp()' in query: return Result({'cutoff': self.cutoff})
        table = next(t for t in self.data if 'FROM ' + t + ' ' in query)
        assert params[:2] == ('dev-org', 'fixture-project')
        rows = self.data[table]
        if 'COUNT(*)' in query:
            assert 'LIMIT' not in query
            return Result(self.overrides.get(table, dict(count=len(rows), invalid_count=0 if rows else None,
                          latest_created_at=max((r['created_at'] for r in rows), default=None))))
        assert 'octet_length' in query and 'LIMIT ' in query
        if 'AS authority_data' in query: assert 'CASE WHEN octet_length' in query
        if len(params) == 4: rows = [r for r in rows if (r['identity'], r['revision']) == tuple(params[2:])]
        elif len(params) == 3:
            if isinstance(params[2], list): rows = [r for r in rows if r['identity'] in params[2]]
            else: rows = [r for r in rows if r['decision_id'] == params[2]]
        elif len(params) == 5:
            pairs = set(zip(params[2], params[3]))
            rows = [r for r in rows if (r['customer_id'], r['sequence']) in pairs and r['consent_policy_id'] == params[4]]
        if 'LIMIT 1' in query and 'LIMIT 1001' not in query:
            return Result(max(rows, key=lambda r: (r['created_at'], r['revision'], r['identity'])) if rows else None)
        return Result(sorted(rows, key=lambda r: (r['created_at'], r['identity'], r['revision'])))


def run(observation='unknown'):
    scope, cutoff, data, start = producer_fixture(observation)
    conn = Connection(data, cutoff)
    return scope, conn, reader.CustomerContactReadonlyReader(connect_factory=lambda tenant: conn), start


@pytest.mark.parametrize('observation,field', [(None, 'reserved'), ('unknown', 'unknown'), ('disputed', 'applied')])
def test_original_nonempty_saved_start_verified_before_projection(observation, field):
    scope, conn, subject, original = run(observation)
    view = subject.read(scope)
    assert view.ledger.frozen_eligible == 2 and getattr(view.ledger, field) == view.ledger.skipped_withdrawn == 1
    assert view.latest_start.content_hash == original.content_hash
    assert view.latest_start.items[0].reservation.status == 'held' and original.items[0].state.value == 'reserved'
    assert view.frequency_policy_count == view.withdrawal_count == 1
    assert view.allowed_commands == [] and 'reason' not in view.model_dump(mode='json', by_alias=True)['latestStart']
    assert not any((view.permit_redemption_allowed, view.contact_resolution_allowed, view.provider_dispatch_allowed, view.send_allowed, view.external_effects_allowed))


def test_real_empty_and_untruncated_saved_revision_counts():
    scope, conn, subject, _ = run()
    for table in conn.data: conn.data[table] = []
    conn.overrides[TABLES['frequency']] = dict(count=9000, invalid_count=0, latest_created_at=conn.cutoff)
    view = subject.read(scope)
    assert view.frequency_policy_count == 9000 and view.withdrawal_count == 0
    assert view.latest_start is None and view.ledger.frozen_eligible == 0 and not view.allowed_commands


@pytest.mark.parametrize('key,value', [('count', True), ('count', -1), ('count', 2**53), ('invalid_count', 1), ('invalid_count', False)])
def test_invalid_counts_never_become_zero_success(key, value):
    scope, conn, subject, _ = run(); entry = dict(count=1, invalid_count=0, latest_created_at=conn.cutoff); entry[key] = value
    conn.overrides[TABLES['frequency']] = entry
    with pytest.raises(reader.CustomerContactReadonlyError): subject.read(scope)


@pytest.mark.parametrize('attribute,value', [('read_only', False), ('autocommit', True), ('isolation_level', IsolationLevel.READ_COMMITTED)])
def test_one_verified_readonly_snapshot_required(attribute, value):
    scope, conn, subject, _ = run(); setattr(conn, attribute, value)
    with pytest.raises(reader.CustomerContactReadonlyError): subject.read(scope)


@pytest.mark.parametrize('mutation', ['missing_reason', 'wrong_reason', 'tenant', 'extra', 'bool_zero', 'missing_zero', 'private_reason', 'future', 'oversize', 'start_hash', 'binding', 'permit', 'attempt', 'reservation', 'reservation_outer', 'withdrawal', 'withdrawal_outer', 'batch_hash', 'policy_hash', 'frequency_hash', 'observation_hash', 'observation_outer', 'observation_unknown', 'skip_observation'])
def test_corrupted_saved_fact_is_stable_failure(mutation):
    scope, conn, subject, _ = run()
    start = conn.data[TABLES['start']][0]; raw = start['authority_data']
    if mutation == 'missing_reason': del raw['reason']
    elif mutation == 'wrong_reason': raw['reason'] += '-changed'
    elif mutation == 'tenant': raw['tenant']['projectId'] = 'foreign'
    elif mutation == 'extra': raw['contactValue'] = 'synthetic-private-value'
    elif mutation == 'bool_zero': raw['sendCount'] = False
    elif mutation == 'missing_zero': del raw['sendCount']
    elif mutation == 'private_reason': raw['reason'] = 'fixture@example.test'
    elif mutation == 'future': start['created_at'] = conn.cutoff + timedelta(seconds=1)
    elif mutation == 'oversize': start['size'] = reader.MAX_ROW_BYTES + 1; start['authority_data'] = None
    elif mutation == 'start_hash': raw['contentHash'] = 'a' * 64
    elif mutation == 'binding': raw['items'][0]['bindingHash'] = 'b' * 64
    elif mutation == 'permit': raw['items'][0]['permit']['rawContactCount'] = 1
    elif mutation == 'attempt': raw['items'][0]['attempt']['outboxIntentHash'] = 'c' * 64
    elif mutation == 'reservation': conn.data[TABLES['reservation']][0]['authority_data']['status'] = 'released'
    elif mutation == 'reservation_outer': conn.data[TABLES['reservation']][0]['customer_id'] = 'different'
    elif mutation == 'withdrawal': conn.data[TABLES['withdrawal']][0]['authority_data']['sequence'] = 11
    elif mutation == 'withdrawal_outer': conn.data[TABLES['withdrawal']][0]['consent_policy_id'] = 'different'
    elif mutation == 'batch_hash': conn.data[TABLES['batch']][-1]['authority_data']['contentHash'] = 'd' * 64
    elif mutation == 'policy_hash': conn.data[TABLES['policy']][0]['authority_data']['purpose'] = 'changed'
    elif mutation == 'frequency_hash': conn.data[TABLES['frequency']][0]['authority_data']['maximumContacts'] = 3
    elif mutation == 'observation_hash': conn.data[TABLES['observation']][0]['authority_data']['contentHash'] = 'e' * 64
    elif mutation == 'observation_outer': conn.data[TABLES['observation']][0]['item_key'] = 'different'
    elif mutation == 'observation_unknown': conn.data[TABLES['observation']][0]['authority_data']['resolvedState'] = 'applied'
    elif mutation == 'skip_observation': conn.data[TABLES['observation']][0]['authority_data']['itemKey'] = 'item-3'
    with pytest.raises(reader.CustomerContactReadonlyError): subject.read(scope)


def test_future_aggregate_not_hidden_by_where_cutoff():
    scope, conn, subject, _ = run()
    conn.overrides[TABLES['withdrawal']] = dict(count=1, invalid_count=0, latest_created_at=conn.cutoff + timedelta(seconds=1))
    with pytest.raises(reader.CustomerContactReadonlyError): subject.read(scope)


def test_observation_limit_rejects_instead_of_truncating():
    scope, conn, subject, _ = run()
    conn.data[TABLES['observation']] *= 257
    with pytest.raises(reader.CustomerContactReadonlyError, match='LIMIT_EXCEEDED'): subject.read(scope)


def test_database_error_is_stable_and_does_not_echo_private_details():
    scope, conn, subject, _ = run()
    def fail(*args): raise psycopg.OperationalError('synthetic-private-database-details')
    conn.execute = fail
    with pytest.raises(reader.CustomerContactReadonlyError, match='CUSTOMER_CONTACT_READ_AUTHORITY_UNAVAILABLE') as error: subject.read(scope)
    assert 'private-database' not in str(error.value)


def test_deadline_checked_between_queries(monkeypatch):
    scope, conn, subject, _ = run(); ticks = iter([0, 11])
    monkeypatch.setattr(reader, 'monotonic', lambda: next(ticks))
    with pytest.raises(reader.CustomerContactReadonlyError, match='LIMIT_EXCEEDED'): subject.read(scope)


@pytest.mark.parametrize('mutation', ['coverage', 'order', 'decision_id', 'unknown_base', 'permit_id', 'outbox', 'skip_sequence', 'extra_ref', 'duplicate'])
def test_rehashed_start_still_must_match_original_producer_and_exact_batch(mutation):
    scope, conn, subject, _ = run()
    saved = conn.data[TABLES['start']][0]
    start = d.CustomerBatchStartDecisionRevision.model_validate(saved['authority_data'])
    if mutation == 'coverage': start.items = start.items[:1]
    elif mutation == 'order': start.items.reverse()
    elif mutation == 'decision_id': start.decision_id = 'forged-start'; saved['identity'] = start.decision_id
    elif mutation == 'unknown_base': start.items[0].state = d.CustomerContactItemState.UNKNOWN
    elif mutation == 'permit_id': start.items[0].permit.permit_id = 'forged-permit'
    elif mutation == 'outbox': start.items[0].attempt.outbox_intent_hash = 'a' * 64
    elif mutation == 'skip_sequence': start.items[1].withdrawal_sequence = 11
    elif mutation == 'extra_ref': start.exact_refs['unexpected'] = start.batch_ref
    elif mutation == 'duplicate': start.items.append(start.items[0].model_copy(deep=True))
    start.ledger = d._ledger(start.items)
    start.content_hash = d.customer_start_signing_hash(start)
    saved.update(authority_data=d.customer_start_authority_data(start), content_hash=start.content_hash)
    with pytest.raises(reader.CustomerContactReadonlyError): subject.read(scope)


@pytest.mark.parametrize('mutation', ['start_ref', 'missing_item', 'skipped_item', 'before_start'])
def test_rehashed_observation_requires_original_start_and_observable_item(mutation):
    scope, conn, subject, original = run()
    saved = conn.data[TABLES['observation']][0]
    value = d.CustomerDispatchObservation.model_validate(saved['authority_data'])
    if mutation == 'start_ref': value.start_decision_ref = value.start_decision_ref.model_copy(update={'content_hash': 'sha256:' + 'a' * 64})
    elif mutation == 'missing_item': value.item_key = 'absent-item'; saved['item_key'] = value.item_key
    elif mutation == 'skipped_item': value.item_key = 'item-3'; saved['item_key'] = value.item_key
    elif mutation == 'before_start': value.observed_at = original.started_at - timedelta(seconds=1); saved['created_at'] = value.observed_at
    request = d.RecordCustomerDispatchObservationRequest.model_validate({name: getattr(value, name) for name in d.RecordCustomerDispatchObservationRequest.model_fields})
    value.content_hash = d.canonical_hash(request.model_dump(mode='json', by_alias=True))
    value.observation_id = 'customer-dispatch-observation-' + value.content_hash[:24]
    saved.update(identity=value.observation_id, authority_data=value.model_dump(mode='json', by_alias=True), content_hash=value.content_hash)
    with pytest.raises(reader.CustomerContactReadonlyError): subject.read(scope)


def test_total_payload_budget_is_checked_on_metadata_before_bulk_transfer():
    scope, conn, subject, _ = run()
    conn.data[TABLES['observation']] *= 8
    for row in conn.data[TABLES['observation']]: row['size'] = reader.MAX_ROW_BYTES
    with pytest.raises(reader.CustomerContactReadonlyError, match='LIMIT_EXCEEDED'): subject.read(scope)
    observed = [query for query, _ in conn.calls if 'FROM ' + TABLES['observation'] + ' ' in query]
    assert len(observed) == 1 and 'AS authority_data' not in observed[0]


def test_original_start_snapshot_is_unchanged_after_projection():
    scope, conn, subject, _ = run()
    before = deepcopy(conn.data)
    result = subject.read(scope)
    assert result.ledger.unknown == 1 and conn.data == before


def test_excessively_nested_driver_json_decode_is_stable_limit_failure():
    scope, conn, subject, _ = run()
    saved = conn.data[TABLES['start']][0]
    original_json = json.dumps(saved['authority_data'])
    deeply_nested_json = original_json[:-1] + ',"padding":' + '[' * 1100 + '0' + ']' * 1100 + '}'
    saved['size'] = len(deeply_nested_json.encode())
    execute = conn.execute
    class JsonResult:
        def fetchone(self):
            # Psycopg JSON decoding can fail while fetching, before a model or
            # privacy validator sees the payload; exercise the real decoder.
            return json.loads(deeply_nested_json)
    def decoding_execute(query, params=None):
        result = execute(query, params)
        if 'FROM ' + TABLES['start'] + ' ' in query and 'AS authority_data' in query: return JsonResult()
        return result
    conn.execute = decoding_execute
    with pytest.raises(reader.CustomerContactReadonlyError, match='LIMIT_EXCEEDED'): subject.read(scope)

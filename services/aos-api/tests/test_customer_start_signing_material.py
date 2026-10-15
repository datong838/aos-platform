"""Private immutable signing material roundtrip, never operational authority."""
from copy import deepcopy
from datetime import UTC
import importlib.util
import json
from pathlib import Path

import pytest

from aos_api import ecommerce_workshop_customer_contact as domain
from aos_api.ecommerce_workshop_customer_contact_store import EcommerceWorkshopCustomerContactStore


def fixture():
    spec = importlib.util.spec_from_file_location('signing_fixture', Path(__file__).parent / 'aip/test_w6_08_customer_contact.py')
    f = importlib.util.module_from_spec(spec); spec.loader.exec_module(f)
    f.SCOPE = f.TenantScope('dev-org', 'fixture-project')
    service, store, batch = f.service_fixture()
    request = f.start_request(batch)
    start = service.start_batch(f.SCOPE, batch.batch_id, request, 'synthetic-operator', now=f.NOW)
    return f, service, store, batch, request, start


def original_hash(item, reason):
    return domain.canonical_hash(dict(batchRef=item.batch_ref, startSequence=item.start_sequence,
                                     exactRefs=item.exact_refs, items=item.items, reason=reason))


class Result:
    def __init__(self, row=None): self.row = row
    def fetchone(self): return deepcopy(self.row)


class Connection:
    def __init__(self): self.rows, self.calls, self.commits = {}, [], 0
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def commit(self): self.commits += 1
    def execute(self, query, params):
        self.calls.append(query)
        if query.startswith('INSERT INTO ecommerce_customer_batch_start_decision_revision'):
            self.rows.setdefault(tuple(params[:4]), dict(authority_data=json.loads(params[-2]), content_hash=params[-3]))
            return Result()
        if query.startswith('SELECT authority_data,content_hash FROM ecommerce_customer_batch_start_decision_revision'):
            return Result(self.rows.get(tuple(params)))
        raise AssertionError('Unexpected SQL in isolated Store probe')


def test_original_hash_and_public_wire_remain_unchanged():
    f, service, store, batch, request, start = fixture()
    assert start.reason == request.reason
    assert start.content_hash == original_hash(start, request.reason)
    wire = start.model_dump(mode='json', by_alias=True)
    assert 'reason' not in wire and request.reason not in repr(start)
    assert 'reason' not in domain.CustomerBatchStartDecisionRevision.model_json_schema(mode='serialization')['properties']
    assert 'reason' in domain.CustomerBatchStartDecisionRevision.model_json_schema(mode='validation')['properties']
    assert service.start_batch(f.SCOPE, batch.batch_id, request, 'synthetic-operator', now=f.NOW) == start
    assert len(store.reservations) == 1 and store.observations == []
    assert start.contact_resolution_count == start.provider_call_count == start.send_count == start.external_effect_count == 0


def test_real_store_serializer_roundtrip_retains_original_signing_material():
    f, _service, _store, batch, request, start = fixture()
    connection = Connection()
    store = EcommerceWorkshopCustomerContactStore(connect_factory=lambda scope: connection)
    restored = store.append_start(f.SCOPE, batch.batch_id, start)
    persisted = next(iter(connection.rows.values()))['authority_data']
    assert persisted['reason'] == request.reason and restored.reason == request.reason
    assert restored.model_dump(mode='json', by_alias=True) == start.model_dump(mode='json', by_alias=True)
    # Datetime's Pydantic UTC representation differs after JSON parsing; the
    # original producer's typed repr must be reconstructed explicitly.
    assert original_hash(restored, request.reason) != start.content_hash
    assert domain.customer_start_signing_hash(restored) == start.content_hash
    before = deepcopy(connection.rows)
    assert store.append_start(f.SCOPE, batch.batch_id, start) == restored
    assert connection.rows == before


def test_legacy_missing_reason_decodes_without_fabricating_or_backfilling():
    f, _service, _store, batch, request, start = fixture()
    legacy_wire = start.model_dump(mode='json', by_alias=True)
    legacy = domain.CustomerBatchStartDecisionRevision.model_validate(legacy_wire)
    assert legacy.reason is None
    assert domain.customer_start_authority_data(legacy) == legacy_wire
    with pytest.raises(domain.CustomerContactBlocked, match='CUSTOMER_START_SIGNING_MATERIAL_UNAVAILABLE'):
        domain.customer_start_signing_hash(legacy)
    connection = Connection()
    key = (*f.SCOPE.key, start.decision_id, start.revision)
    connection.rows[key] = dict(authority_data=legacy_wire, content_hash=start.content_hash)
    before = deepcopy(connection.rows)
    restored = EcommerceWorkshopCustomerContactStore(connect_factory=lambda scope: connection).append_start(f.SCOPE, batch.batch_id, start)
    assert restored.reason is None and connection.rows == before


@pytest.mark.parametrize('private_reason', ['fixture@example.test', '13812345678', 'Bearer fixture-private-token'])
def test_sensitive_reason_denied_before_any_store_or_batch_access(private_reason):
    f, _service, _store, batch, request, _start = fixture()
    class Forbidden:
        def __getattr__(self, name): raise AssertionError('Sensitive reason reached Store: ' + name)
    service = domain.EcommerceWorkshopCustomerContactService(Forbidden(), Forbidden())
    with pytest.raises(domain.CustomerContactBlocked) as error:
        service.start_batch(f.SCOPE, batch.batch_id, request.model_copy(update={'reason': private_reason}), 'synthetic-operator', now=f.NOW)
    assert str(error.value) == 'CUSTOMER_START_SIGNING_REASON_SENSITIVE'
    assert private_reason not in str(error.value)


def test_reconstruction_is_pure_and_does_not_accept_wrong_material_as_same_hash():
    _f, _service, _store, _batch, request, start = fixture()
    saved = domain.customer_start_authority_data(start)
    restored = domain.CustomerBatchStartDecisionRevision.model_validate(saved)
    before = deepcopy(saved)
    assert domain.customer_start_signing_hash(restored) == start.content_hash
    assert domain.customer_start_authority_data(restored) == before
    assert domain.customer_start_signing_hash(restored.model_copy(update={'reason': request.reason + '-changed'})) != start.content_hash
    changed = restored.model_copy(deep=True)
    changed.items[0].reservation.created_at = changed.items[0].reservation.created_at.replace(year=2025)
    assert domain.customer_start_signing_hash(changed) != start.content_hash


def test_projection_keeps_private_material_off_public_dto_and_original_start_immutable():
    f, service, store, _batch, request, start = fixture()
    binding = start.items[0]
    receipt = f.ref('ActionReceipt', 'synthetic-receipt', 'f')
    store.receipts[(*f.SCOPE.key, receipt.resource_id)] = (receipt.content_hash, binding.binding_hash)
    service.record_dispatch_observation(f.SCOPE, f.RecordCustomerDispatchObservationRequest(
        startDecisionRef=f.full_ref('CustomerBatchStartDecisionRevision', start.decision_id, start.content_hash),
        itemKey=binding.item_key, actionReceiptRef=receipt, state='unknown', observedAt=f.NOW))
    view = service.contribution_view(f.SCOPE, now=f.NOW)
    assert view.latest_start.reason == request.reason and 'reason' not in view.model_dump(mode='json', by_alias=True)['latestStart']
    assert view.latest_start.items[0].state.value == 'unknown' and start.items[0].state.value == 'reserved'
    assert view.latest_start.items[0].reservation.status == 'held'
    assert view.latest_start.content_hash == start.content_hash and view.ledger.unknown == 1


def test_original_production_resolvers_stay_blocked():
    store = EcommerceWorkshopCustomerContactStore(connect_factory=lambda scope: None)
    with pytest.raises(domain.CustomerContactBlocked, match='START_AUTHORITY_RESOLVER_UNAVAILABLE'):
        store.require_start_authorities(None, None)
    with pytest.raises(domain.CustomerContactBlocked, match='ACTION_RECEIPT_RESOLVER_UNAVAILABLE'):
        store.require_action_receipt(None, None, 'a' * 64)

"""Customer saved closure contract; synthetic authority is never live approval."""
from datetime import timedelta
import json

import psycopg
import pytest
from psycopg import IsolationLevel

from aos_api.ecommerce_workshop_three_module_closure import (
    BindThreeModuleEffectRequest, BindThreeModuleHandoffRequest,
    BindThreeModuleUsageRequest, CompileThreeModuleClosureRequest,
    EcommerceWorkshopThreeModuleClosureService,
)
from tests.test_ecommerce_three_module_closure_readonly import (
    SCOPE, NOW, CUTOFF, TABLES, ProducerFixture, Connection, Cursor, ref,
)


def customer_rows(scope=SCOPE):
    producer = ProducerFixture()
    service = EcommerceWorkshopThreeModuleClosureService(producer)
    closure = service.compile(scope, CompileThreeModuleClosureRequest(
        module='customer', sourceRef=ref('CustomerBatchStartDecisionRevision', 'customer-fixture')),
        'fixture-actor', now=NOW)
    exact = service._ref('ThreeModuleClosureRevision', closure.closure_id, closure.content_hash)
    values = dict(closure=closure,
        usage=service.bind_usage(scope, BindThreeModuleUsageRequest(closureRef=exact, usageReceiptId='fixture-usage'), now=NOW),
        effect=service.bind_effect(scope, BindThreeModuleEffectRequest(closureRef=exact, effectReviewId='fixture-effect'), now=NOW),
        handoff=service.bind_handoff(scope, BindThreeModuleHandoffRequest(closureRef=exact, handoffId='fixture-handoff'), now=NOW))
    rows = {}
    for kind, value in values.items():
        raw = value.model_dump(mode='json', by_alias=True)
        rows[kind] = dict(org_id=scope.org_id, project_id=scope.project_id,
            resource_id=closure.closure_id if kind == 'closure' else value.binding_id,
            closure_id=closure.closure_id, revision=1, module='customer' if kind == 'closure' else None,
            source_id=closure.source_ref.resource_id if kind == 'closure' else None,
            content_hash=value.content_hash, created_at=NOW,
            payload_bytes=len(json.dumps(raw).encode()), authority_data=raw)
    return rows


class CustomerConnection(Connection):
    def execute(self, sql, params=None):
        if sql.startswith('SET LOCAL'):
            assert sql in ("SET LOCAL statement_timeout='3000ms'", "SET LOCAL lock_timeout='500ms'")
            self.queries.append((sql, params)); return Cursor(None)
        if 'FROM ecommerce_three_module_closure_revision ' in sql:
            assert params == (*self.scope.key, 'customer')
        return super().execute(sql, params)


def reader(conn):
    from aos_api.ecommerce_customer_closure_readonly import CustomerClosureReadonlyReader
    return CustomerClosureReadonlyReader(connect_factory=lambda scope: conn)


def denied(conn):
    from aos_api.ecommerce_customer_closure_readonly import CustomerClosureReadonlyError
    with pytest.raises(CustomerClosureReadonlyError) as caught:
        reader(conn).read(SCOPE)
    assert caught.value.code.startswith('CUSTOMER_CLOSURE_READ_')
    return caught.value.code


def test_empty_is_true_missing_history_and_no_commands():
    conn = CustomerConnection({}); value = reader(conn).read(SCOPE)
    assert value.latest_closure is value.latest_usage is value.latest_effect is value.latest_handoff is None
    assert len(value.blockers) == 4 and value.evaluated_at == CUTOFF
    assert value.allowed_commands == [] and not value.handoff_consume_allowed
    assert not value.memory_promotion_allowed and not value.external_effects_allowed
    assert len([s for s, _ in conn.queries if s.startswith('SELECT')]) == 2


def test_actual_original_producer_hashes_preserve_five_independent_axes():
    conn = CustomerConnection(customer_rows()); value = reader(conn).read(SCOPE)
    assert value.module.value == 'customer' and value.primary_colleague == '私域管家'
    assert value.latest_closure.source_ref.resource_type == 'CustomerBatchStartDecisionRevision'
    assert value.latest_closure.ledger.unknown == 1 and value.latest_closure.ledger.state.value == 'partial'
    assert value.latest_usage.quantity is None and value.latest_usage.quality == 'unknown'
    assert value.latest_effect.accepted and not value.latest_effect.effect_completed
    assert value.latest_effect.cutoff_at > CUTOFF
    assert value.latest_handoff.business_decision == 'request_more'
    assert value.latest_handoff.task_ref['revision'] == '1'
    assert value.allowed_commands == [] and not value.external_effects_allowed
    selects = [s for s, _ in conn.queries if s.startswith('SELECT')]
    assert len(selects) == 5
    assert all('CASE WHEN' in s and 'octet_length' in s and 'LIMIT 1' in s for s in selects[1:])


@pytest.mark.parametrize('kind', list(TABLES))
@pytest.mark.parametrize('field,value', [('org_id', 'foreign'), ('project_id', 'foreign'),
    ('revision', True), ('resource_id', 'foreign'), ('content_hash', 'b' * 64),
    ('module', 'price'), ('created_at', CUTOFF + timedelta(seconds=1))])
def test_each_outer_authority_is_checked(kind, field, value):
    rows = customer_rows(); rows[kind][field] = value
    assert denied(CustomerConnection(rows)).endswith('AUTHORITY_DRIFT')


@pytest.mark.parametrize('kind', list(TABLES))
def test_single_payload_limit_before_decode(kind):
    rows = customer_rows(); rows[kind].update(payload_bytes=65537, authority_data=None)
    assert denied(CustomerConnection(rows)).endswith('LIMIT_EXCEEDED')


@pytest.mark.parametrize('kind,field,value', [('closure', 'revision', 1.0),
    ('effect', 'sampleCount', True), ('effect', 'minSample', 10.0),
    ('effect', 'accepted', 1), ('handoff', 'disclosureRefCount', False),
    ('usage', 'adjustmentTotal', float('inf')), ('usage', 'quantity', float('nan'))])
def test_coercion_or_nonfinite_never_fabricates_canonical_evidence(kind, field, value):
    rows = customer_rows(); rows[kind]['authority_data'][field] = value
    denied(CustomerConnection(rows))


@pytest.mark.parametrize('kind', list(TABLES))
def test_nested_tenant_and_unknown_field_fail(kind):
    rows = customer_rows(); rows[kind]['authority_data']['tenant']['projectId'] = 'foreign'
    denied(CustomerConnection(rows))
    rows = customer_rows(); rows[kind]['authority_data']['unrecognized'] = 'not canonical'
    denied(CustomerConnection(rows))


@pytest.mark.parametrize('kind', ['usage', 'effect', 'handoff'])
def test_exact_binding_never_borrows_other_closure(kind):
    rows = customer_rows(); rows[kind]['authority_data']['closureRef']['contentHash'] = 'sha256:' + 'b' * 64
    denied(CustomerConnection(rows))


@pytest.mark.parametrize('field,value', [('read_only', False), ('autocommit', True),
    ('isolation_level', IsolationLevel.READ_COMMITTED)])
def test_transaction_required_before_sql(field, value):
    conn = CustomerConnection({}); setattr(conn, field, value)
    assert denied(conn).endswith('UNAVAILABLE') and not conn.queries


def test_db_exception_is_not_empty_or_leaked():
    conn = CustomerConnection({})
    def fail(*args): raise psycopg.OperationalError('private credential detail')
    conn.execute = fail
    assert denied(conn) == 'CUSTOMER_CLOSURE_READ_UNAVAILABLE'


@pytest.mark.parametrize('actor', ['13800138000', 'operator@example.invalid', 'providerPayload-in-actor'])
def test_private_free_text_never_reaches_public_output(actor):
    rows = customer_rows(); rows['closure']['authority_data']['compiledBy'] = actor
    assert denied(CustomerConnection(rows)).split('_')[-1] in {'UNAVAILABLE', 'UNSUPPORTED'}


def test_deep_driver_json_fails_limit_not_unhandled_error():
    conn = CustomerConnection({})
    def fail(*args): return json.loads('[' * 1100 + '0' + ']' * 1100)
    conn.execute = fail
    assert denied(conn) == 'CUSTOMER_CLOSURE_READ_LIMIT_EXCEEDED'


def test_deadline_is_bounded(monkeypatch):
    from aos_api import ecommerce_customer_closure_readonly as module
    ticks = iter([0, 11]); monkeypatch.setattr(module, 'monotonic', lambda: next(ticks))
    assert denied(CustomerConnection({})).endswith('LIMIT_EXCEEDED')


def test_original_customer_start_observation_and_store_status_mapping(monkeypatch):
    from tests.aip import test_w6_08_customer_contact as fixture
    from aos_api import ecommerce_workshop_customer_contact as contact
    from aos_api.ecommerce_workshop_three_module_closure import ThreeModule
    from aos_api.ecommerce_workshop_three_module_closure_store import EcommerceWorkshopThreeModuleClosureStore
    monkeypatch.setattr(fixture, 'SCOPE', SCOPE)
    service, store, batch = fixture.service_fixture()
    service.create_frequency_policy(SCOPE, fixture.CreateCustomerFrequencyPolicyRequest(
        policyId='frequency-policy', revision=1, channel='wecom', purpose='retention', timezone='Asia/Shanghai',
        quietHoursStart='22:00', quietHoursEnd='08:00', rollingWindowHours=168, maximumContacts=2), 'fixture-actor', now=fixture.NOW)
    started = service.start_batch(SCOPE, batch.batch_id, fixture.start_request(batch), 'fixture-actor', now=fixture.NOW)
    exact = fixture.full_ref('CustomerBatchStartDecisionRevision', started.decision_id, started.content_hash)
    receipt = fixture.ref('ActionReceipt', 'fixture-receipt', 'f')
    store.receipts[(*SCOPE.key, receipt.resource_id)] = (receipt.content_hash, started.items[0].binding_hash)
    observation = service.record_dispatch_observation(SCOPE, fixture.RecordCustomerDispatchObservationRequest(
        startDecisionRef=exact, itemKey=started.items[0].item_key, actionReceiptRef=receipt,
        state='unknown', observedAt=fixture.NOW + timedelta(seconds=1)))
    class SourceCursor:
        def __init__(self, rows): self.rows = rows
        def fetchone(self): return self.rows[0]
        def fetchall(self): return self.rows
    class SourceConnection:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def execute(self, sql, params):
            assert sql.startswith('SELECT') and params[:2] == SCOPE.key
            if 'FROM ecommerce_customer_batch_start_decision_revision ' in sql:
                return SourceCursor([dict(authority_data=contact.customer_start_authority_data(started), content_hash=started.content_hash)])
            assert 'FROM ecommerce_customer_dispatch_observation ' in sql
            return SourceCursor([dict(authority_data=observation.model_dump(mode='json', by_alias=True))])
    original = EcommerceWorkshopThreeModuleClosureStore(read_connect_factory=lambda scope: SourceConnection())
    items = original.resolve_domain_items(SCOPE, ThreeModule.CUSTOMER, exact)
    assert len(items) == 1 and items[0].original_status == 'unknown'
    assert items[0].canonical_outcome.value == 'unknown'
    assert items[0].receipt_ref.model_dump(mode='json', by_alias=True) == receipt.model_dump(mode='json', by_alias=True)
    original.resolve_domain_items = lambda *args: items
    original.append_closure = lambda scope, value: value
    closure = EcommerceWorkshopThreeModuleClosureService(original).compile(SCOPE,
        CompileThreeModuleClosureRequest(module='customer', sourceRef=exact.model_dump(mode='json', by_alias=True)),
        'fixture-actor', now=NOW)
    assert closure.ledger.unknown == 1 and closure.ledger.succeeded == 0

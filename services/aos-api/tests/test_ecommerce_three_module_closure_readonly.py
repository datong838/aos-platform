from datetime import UTC, datetime, timedelta
import json

import psycopg
import pytest
from psycopg import IsolationLevel

from aos_api.ecommerce_workshop_three_module_closure import (
    BindThreeModuleEffectRequest, BindThreeModuleHandoffRequest,
    BindThreeModuleUsageRequest, ClosureExactRef, CompileThreeModuleClosureRequest,
    EcommerceWorkshopThreeModuleClosureService, ThreeModuleItemOutcome,
)
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope('dev-org', 'fixture-project')
NOW = datetime(2026, 10, 15, 1, tzinfo=UTC)
CUTOFF = NOW + timedelta(seconds=10)
TABLES = dict(closure='ecommerce_three_module_closure_revision',
              usage='ecommerce_three_module_usage_binding_revision',
              effect='ecommerce_three_module_effect_binding_revision',
              handoff='ecommerce_three_module_handoff_binding_revision')


def ref(kind, identity):
    return ClosureExactRef(resourceType=kind, resourceId=identity, revision=1,
                           contentHash='sha256:' + 'a' * 64, receiptId='receipt-' + identity)


class ProducerFixture:
    """No DB or real approval: exercise the unchanged original typed producer."""
    def resolve_domain_items(self, scope, module, source):
        return [ThreeModuleItemOutcome(
            itemKey=key, originalStatus=status, canonicalOutcome=outcome,
            originalRef=source.model_copy(update={'resource_id': source.resource_id + ':' + key}),
        ) for key, status, outcome in [('lane-1', 'applied', 'succeeded'),
                                     ('lane-2', 'unknown', 'unknown')]]

    def append_closure(self, scope, value):
        self.closure = value
        return value

    def require_closure(self, scope, exact):
        return self.closure

    def resolve_usage(self, scope, identity):
        return dict(usageReceiptRef=ref('UsageReceipt', identity), lineageId='fixture-lineage',
                    quality='unknown', quantity=None, unit='tokens',
                    adjustmentTotal=0.0, settlement='unknown')

    def resolve_effect(self, scope, identity, source):
        return dict(effectReviewRef=ref('EffectReviewRevision', identity),
                    maturityStatus='immature', accepted=True, effectCompleted=False,
                    sampleCount=3, minSample=10, cutoffAt=NOW + timedelta(days=1), observedAt=NOW)

    def resolve_handoff(self, scope, identity):
        return dict(handoffRef=ref('HandoffEnvelope', identity), transportStatus='consumed',
                    businessDecision='request_more', disclosureRefCount=0,
                    taskRef=dict(resourceType='Task', resourceId='fixture-task', revision='1', authority='postgresql'),
                    taskRunRef=dict(resourceType='TaskRun', resourceId='fixture-run', revision='1', authority='postgresql'))

    def append_usage_binding(self, scope, value): return value
    def append_effect_binding(self, scope, value): return value
    def append_handoff_binding(self, scope, value): return value


def authority_rows(module='creator', scope=SCOPE):
    store = ProducerFixture()
    service = EcommerceWorkshopThreeModuleClosureService(store)
    closure = service.compile(scope, CompileThreeModuleClosureRequest(
        module=module, sourceRef=ref('CreatorBatchStartDecisionRevision' if module == 'creator' else 'PriceDispositionRevision', 'fixture-decision')),
        'fixture-actor', now=NOW)
    exact = service._ref('ThreeModuleClosureRevision', closure.closure_id, closure.content_hash)
    values = dict(closure=closure,
                  usage=service.bind_usage(scope, BindThreeModuleUsageRequest(closureRef=exact, usageReceiptId='fixture-usage'), now=NOW),
                  effect=service.bind_effect(scope, BindThreeModuleEffectRequest(closureRef=exact, effectReviewId='fixture-effect'), now=NOW),
                  handoff=service.bind_handoff(scope, BindThreeModuleHandoffRequest(closureRef=exact, handoffId='fixture-handoff'), now=NOW))
    rows = {}
    for kind, value in values.items():
        payload = value.model_dump(mode='json', by_alias=True)
        rows[kind] = dict(org_id=scope.org_id, project_id=scope.project_id,
                          resource_id=value.closure_id if kind == 'closure' else value.binding_id,
                          closure_id=closure.closure_id, revision=1,
                          module=module if kind == 'closure' else None,
                          source_id=closure.source_ref.resource_id if kind == 'closure' else None,
                          content_hash=value.content_hash, created_at=NOW,
                          payload_bytes=len(json.dumps(payload).encode()), authority_data=payload)
    return rows


class Cursor:
    def __init__(self, row): self.row = row
    def fetchone(self): return self.row


class Connection:
    read_only = True
    autocommit = False
    isolation_level = IsolationLevel.REPEATABLE_READ

    def __init__(self, rows, scope=SCOPE): self.rows, self.queries, self.scope = rows, [], scope
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, sql, params=None):
        self.queries.append((sql, params))
        assert sql.lstrip().upper().startswith('SELECT')
        if 'transaction_timestamp()' in sql: return Cursor({'cutoff': CUTOFF})
        for kind, table in TABLES.items():
            if 'FROM ' + table + ' ' in sql:
                assert tuple(params[:2]) == self.scope.key
                return Cursor(self.rows.get(kind))
        raise AssertionError('unexpected table')
    def commit(self): raise AssertionError('read cannot commit')


def reader(conn):
    from aos_api.ecommerce_three_module_closure_readonly import CreatorClosureReadonlyReader
    def factory(scope):
        assert scope == SCOPE
        return conn
    return CreatorClosureReadonlyReader(connect_factory=factory)


def denied(conn):
    from aos_api.ecommerce_three_module_closure_readonly import CreatorClosureReadonlyError
    with pytest.raises(CreatorClosureReadonlyError) as caught:
        reader(conn).read(SCOPE)
    assert str(caught.value).startswith('CREATOR_CLOSURE_READ_')
    return caught.value


def test_empty_has_four_real_gaps_and_no_commands():
    conn = Connection({})
    view = reader(conn).read(SCOPE)
    assert view.latest_closure is None
    assert len(view.blockers) == 4 and view.allowed_commands == []
    assert view.evaluated_at == CUTOFF and not view.external_effects_allowed
    assert not view.handoff_consume_allowed and not view.memory_promotion_allowed


def test_original_producer_hashes_null_module_future_immature_window():
    conn = Connection(authority_rows())
    view = reader(conn).read(SCOPE)
    assert view.latest_closure.ledger.state.value == 'partial'
    assert view.latest_usage.quantity is None
    assert view.latest_effect.cutoff_at > CUTOFF and not view.latest_effect.effect_completed
    assert view.latest_handoff.business_decision == 'request_more'
    assert view.allowed_commands == []
    assert len(conn.queries) == 5
    assert all('CASE WHEN' in sql and 'octet_length' in sql and 'LIMIT 1' in sql
               for sql, _ in conn.queries[1:])


@pytest.mark.parametrize('kind', list(TABLES))
@pytest.mark.parametrize('field,value', [('org_id', 'foreign'), ('project_id', 'foreign'),
                                        ('revision', True), ('resource_id', 'foreign'),
                                        ('content_hash', 'b' * 64), ('module', 'price'),
                                        ('created_at', CUTOFF + timedelta(seconds=1))])
def test_outer_authority_drift_is_not_empty(kind, field, value):
    rows = authority_rows(); rows[kind][field] = value
    denied(Connection(rows))


@pytest.mark.parametrize('kind', list(TABLES))
def test_nested_tenant_drift(kind):
    rows = authority_rows(); rows[kind]['authority_data']['tenant']['projectId'] = 'foreign'
    denied(Connection(rows))


@pytest.mark.parametrize('kind', ['usage', 'effect', 'handoff'])
def test_binding_ref_cannot_borrow_another_closure(kind):
    rows = authority_rows(); rows[kind]['authority_data']['closureRef']['resourceId'] = 'foreign'
    denied(Connection(rows))


def test_ledger_and_hash_are_both_checked():
    rows = authority_rows(); rows['closure']['authority_data']['ledger'] = {
        'total': 0, 'inProgress': 0, 'succeeded': 0, 'failed': 0, 'unknown': 0,
        'disputed': 0, 'skipped': 0, 'state': 'empty'}
    denied(Connection(rows))


@pytest.mark.parametrize('kind', list(TABLES))
def test_sql_oversize_sentinel_fails_before_decode(kind):
    rows = authority_rows(); rows[kind]['payload_bytes'] = 64 * 1024 + 1
    rows[kind]['authority_data'] = None
    error = denied(Connection(rows))
    assert 'LIMIT' in error.code


@pytest.mark.parametrize('field,value', [('read_only', False), ('autocommit', True),
                                        ('isolation_level', IsolationLevel.READ_COMMITTED)])
def test_wrong_transaction_is_rejected(field, value):
    conn = Connection({}); setattr(conn, field, value)
    denied(conn); assert not conn.queries


def test_backend_exception_never_leaks_sql_or_secret():
    conn = Connection({})
    def fail(*args): raise psycopg.OperationalError('private backend detail')
    conn.execute = fail
    assert 'private' not in str(denied(conn))


def test_legacy_producer_remains_unchanged():
    store = ProducerFixture()
    store.latest_bindings = lambda *args: dict(closure=None, usage=None, effect=None, handoff=None)
    view = EcommerceWorkshopThreeModuleClosureService(store).contribution_view(SCOPE, 'creator')
    assert len(view.allowed_commands) == 4


@pytest.mark.parametrize('actor', ['operator@example.invalid', '13800138000'])
def test_sensitive_actor_is_not_returned_even_with_valid_producer_hash(actor):
    rows = authority_rows(); rows['closure']['authority_data']['compiledBy'] = actor
    assert 'PRIVACY' in denied(Connection(rows)).code


def test_signed_arbitrary_handoff_ref_extension_is_rejected(monkeypatch):
    original = ProducerFixture.resolve_handoff
    def extended(self, scope, identity):
        value = original(self, scope, identity)
        value['taskRef']['protectedContact'] = 'must-not-be-disclosed'
        return value
    monkeypatch.setattr(ProducerFixture, 'resolve_handoff', extended)
    denied(Connection(authority_rows()))


def test_signed_wrong_task_ref_kind_is_rejected(monkeypatch):
    original = ProducerFixture.resolve_handoff
    def wrong(self, scope, identity):
        value = original(self, scope, identity)
        value['taskRunRef']['resourceType'] = 'ProtectedContact'
        return value
    monkeypatch.setattr(ProducerFixture, 'resolve_handoff', wrong)
    assert 'CONTENT' in denied(Connection(authority_rows())).code


def test_duplicate_signed_items_cannot_double_count(monkeypatch):
    original = ProducerFixture.resolve_domain_items
    def duplicated(self, scope, module, source):
        items = original(self, scope, module, source)
        return [items[0], items[0]]
    monkeypatch.setattr(ProducerFixture, 'resolve_domain_items', duplicated)
    denied(Connection(authority_rows()))


@pytest.mark.parametrize('method,key', [('resolve_usage', 'usageReceiptRef'),
    ('resolve_effect', 'effectReviewRef'), ('resolve_handoff', 'handoffRef')])
def test_signed_binding_ref_cannot_claim_an_unrelated_authority_kind(monkeypatch, method, key):
    original = getattr(ProducerFixture, method)
    def wrong(self, *args):
        value = original(self, *args)
        value[key] = ref('ProtectedContact', 'unrelated-fixture')
        return value
    monkeypatch.setattr(ProducerFixture, method, wrong)
    denied(Connection(authority_rows()))


class PriceConnection(Connection):
    def execute(self, sql, params=None):
        if sql.startswith('SET LOCAL'):
            assert sql in ("SET LOCAL statement_timeout='3000ms'", "SET LOCAL lock_timeout='500ms'")
            self.queries.append((sql, params))
            return Cursor(None)
        if 'FROM ecommerce_three_module_closure_revision ' in sql:
            assert params == (*self.scope.key, 'price')
        return super().execute(sql, params)


def price_reader(conn):
    from aos_api.ecommerce_three_module_closure_readonly import PriceClosureReadonlyReader
    return PriceClosureReadonlyReader(connect_factory=lambda scope: conn)


def price_denied(conn):
    from aos_api.ecommerce_three_module_closure_readonly import PriceClosureReadonlyError
    with pytest.raises(PriceClosureReadonlyError) as caught:
        price_reader(conn).read(SCOPE)
    assert caught.value.code.startswith('PRICE_CLOSURE_READ_')
    return caught.value


def test_price_closure_reads_original_producer_five_axes_without_commands():
    conn = PriceConnection(authority_rows('price'))
    view = price_reader(conn).read(SCOPE)
    assert view.module.value == 'price' and view.primary_colleague == '数据参谋'
    assert view.latest_closure.source_ref.resource_type == 'PriceDispositionRevision'
    assert view.latest_closure.ledger.state.value == 'partial'
    assert view.latest_usage.quantity is None and view.latest_usage.settlement == 'unknown'
    assert view.latest_effect.accepted and not view.latest_effect.effect_completed
    assert view.latest_effect.cutoff_at > CUTOFF
    assert view.latest_handoff.transport_status == 'consumed'
    assert view.latest_handoff.business_decision == 'request_more'
    assert view.allowed_commands == [] and not view.handoff_consume_allowed
    assert not view.memory_promotion_allowed and not view.external_effects_allowed
    selects = [s for s, _ in conn.queries if s.lstrip().startswith('SELECT')]
    assert len(selects) == 5
    assert all('CASE WHEN' in s and 'LIMIT 1' in s for s in selects[1:])


def test_price_true_empty_snapshot_has_four_gaps():
    view = price_reader(PriceConnection({})).read(SCOPE)
    assert view.latest_closure is view.latest_usage is view.latest_effect is view.latest_handoff is None
    assert len(view.blockers) == 4 and view.allowed_commands == []


@pytest.mark.parametrize('kind', list(TABLES))
@pytest.mark.parametrize('field,value', [('org_id', 'foreign'), ('project_id', 'foreign'),
    ('revision', True), ('resource_id', 'foreign'), ('content_hash', 'b' * 64),
    ('module', 'creator'), ('created_at', CUTOFF + timedelta(seconds=1))])
def test_price_outer_drift_never_returns_an_empty_success(kind, field, value):
    rows = authority_rows('price'); rows[kind][field] = value
    price_denied(PriceConnection(rows))


@pytest.mark.parametrize('kind', list(TABLES))
def test_price_payload_size_is_sql_guarded(kind):
    rows = authority_rows('price'); rows[kind]['payload_bytes'] = 64 * 1024 + 1
    rows[kind]['authority_data'] = None
    assert 'LIMIT' in price_denied(PriceConnection(rows)).code


@pytest.mark.parametrize('kind,field', [('usage', 'quantity'), ('usage', 'adjustmentTotal'),
    ('handoff', 'businessDecision')])
def test_price_raw_cannot_omit_producer_fields_even_if_defaults_would_match(kind, field):
    rows = authority_rows('price'); del rows[kind]['authority_data'][field]
    price_denied(PriceConnection(rows))


@pytest.mark.parametrize('kind,field,value', [('effect', 'sampleCount', 3.0), ('effect', 'minSample', True),
    ('handoff', 'disclosureRefCount', False), ('usage', 'adjustmentTotal', False),
    ('usage', 'quantity', float('nan')), ('usage', 'quantity', 10 ** 500), ('closure', 'revision', 1.0)])
def test_price_strict_numbers_cannot_be_coerced(kind, field, value):
    rows = authority_rows('price'); rows[kind]['authority_data'][field] = value
    price_denied(PriceConnection(rows))


def test_price_cannot_read_creator_source_type_or_closure():
    price_denied(PriceConnection(authority_rows()))


@pytest.mark.parametrize('kind', ['usage', 'effect', 'handoff'])
def test_price_binding_requires_exact_same_saved_closure(kind):
    rows = authority_rows('price'); rows[kind]['authority_data']['closureRef']['contentHash'] = 'sha256:' + 'b' * 64
    price_denied(PriceConnection(rows))


def test_price_database_failure_is_stable_and_does_not_leak():
    conn = PriceConnection({})
    def fail(*args): raise psycopg.OperationalError('private database detail')
    conn.execute = fail
    error = price_denied(conn)
    assert error.code == 'PRICE_CLOSURE_READ_UNAVAILABLE' and 'private' not in str(error)


@pytest.mark.parametrize('actor', ['operator@example.invalid', '13800138000', 'providerPayload-in-actor'])
def test_price_public_projection_never_exposes_private_content(actor):
    rows = authority_rows('price'); rows['closure']['authority_data']['compiledBy'] = actor
    price_denied(PriceConnection(rows))


def test_price_view_does_not_rewrite_creator_default_entry():
    price_reader(PriceConnection(authority_rows('price'))).read(SCOPE)
    creator = reader(Connection(authority_rows())).read(SCOPE)
    assert creator.module.value == 'creator'
    assert creator.latest_closure.source_ref.resource_type == 'CreatorBatchStartDecisionRevision'

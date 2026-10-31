from contextlib import contextmanager
from types import SimpleNamespace
from uuid import UUID

import pytest

from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
from aos_api.ecommerce_growth_lifecycle import EcommerceGrowthDisableDependent
from aos_api.tenant_scope import TenantScope
from test_ecommerce_growth_registration_contracts import payload
from test_ecommerce_growth_registration_http import harness as original_harness


TARGET = payload()['installationRef']['installationId']
OLD = '99999999-9999-4999-8999-999999999999'
RUNTIME = UUID('77777777-7777-4777-8777-777777777777')
SCOPE = TenantScope('org-org', 'dev-project')


@pytest.fixture
def setup(monkeypatch):
    p = payload()
    snapshot = [dict(operationId=o, handlerKind='legacy', installationId=None, generation=None,
        executionEpoch=None, operationFence=True, revision=340, cutoverGroupId=p['groupId'],
        cutoverGroupRevision=367) for o in sorted(ECOMMERCE_GROWTH_OPERATIONS)]
    names = dict(operationId='operation_id', handlerKind='handler_kind', installationId='installation_id',
        generation='generation', executionEpoch='execution_epoch', operationFence='operation_fence',
        revision='revision', cutoverGroupId='cutover_group_id', cutoverGroupRevision='cutover_group_revision')
    binding = dict(generation=p['generation'], revision=4, execution_epoch=3, config_ref=p['configRef'],
        enabled=True, operation_fence=False, desired_state='enabled', observed_state='ready')
    candidate = dict(runtime_operation_id=RUNTIME, target_installation_id=OLD,
        target_generation=UUID('88888888-8888-4888-8888-888888888888'), fenced_group_revision=366)
    state = SimpleNamespace(snapshot=snapshot, binding=binding, candidates=[candidate], queries=[],
        permissions=[], validated=[], denied=None, drain=False, resources=False, corrupt=False)
    class Result:
        def __init__(self, one=None, many=()): self.one, self.many = one, many
        def fetchone(self): return self.one
        def fetchall(self): return self.many
    class Connection:
        def execute(self, sql, params=()):
            state.queries.append((sql, params))
            assert sql.lstrip().upper().startswith('SELECT'), 'preparation must not mutate'
            if 'FROM public.extension_runtime_binding' in sql: return Result(state.binding)
            if 'FROM public.extension_operation_dispatch_binding' in sql:
                return Result(many=[{names[k]:v for k,v in x.items()} for x in state.snapshot])
            if 'FROM public.extension_dispatch_lifecycle_operation l' in sql: return Result(many=state.candidates)
            if 'FROM public.extension_dispatch_lifecycle_receipt r' in sql: return Result({'fixture': True})
            if 'AS running' in sql:
                return Result(dict(running=int(state.drain), claimed_occurrences=0, unresolved_attempts=0))
            if 'AS claim_pending' in sql: return Result(dict(claim_pending=False, resources_pending=state.resources))
            raise AssertionError(sql)
    @contextmanager
    def transaction(scope):
        assert scope == SCOPE
        yield Connection()
    record = SimpleNamespace(state='active', current=SimpleNamespace(revision=5,
        lock_hash=p['installationRef']['lockHash'], overlay_revision=p['installationRef']['overlayRevision']))
    def authorize(conn, scope, installation_id, actor):
        state.permissions.append(installation_id)
        if installation_id == state.denied: raise PermissionError('private-sentinel')
        return SimpleNamespace(record=record)
    def decode(scope, row, *, replayed):
        if state.corrupt: raise ValueError('private-sentinel')
        return SimpleNamespace(phase='detach', status='detached', receipt_id=UUID('55555555-5555-4555-8555-555555555555'),
            content_hash='sha256:'+'5'*64, dispatch_snapshot=tuple(state.snapshot))
    monkeypatch.setattr(EcommerceGrowthDisableDependent, '_receipt', staticmethod(decode))
    state.owner = SimpleNamespace(_identity=lambda scope,actor:None, _transaction=transaction,
        _require_current_transaction=lambda conn,scope:None, _authorize_receipt_access=authorize,
        validate_current_authority_in_transaction=lambda conn,**kw:state.validated.append(kw))
    return state


def prepare(state):
    from aos_api.ecommerce_growth_successor_preparation import prepare_successor_registration
    return prepare_successor_registration(state.owner, scope=SCOPE, installation_id=TARGET,
        idempotency_key='prepare-one', actor='signed-user').model_dump(mode='json', by_alias=True)


def test_builds_strict_command_from_authorized_current_materials(setup):
    r = prepare(setup)
    assert r['ready'] and r['executable'] is False and not r['reasons']
    assert setup.permissions == [TARGET, OLD]
    c = r['options'][0]['command']
    assert c['registration'] == {**payload(), 'idempotencyKey':'prepare-one'}
    assert c['expectedGroupRevision'] == 367
    assert c['predecessorDetachReceiptRef']['resourceType'] == 'DispatchDisableDetachReceipt'
    assert len(setup.validated) == 1 and setup.validated[0]['actor'] == 'signed-user'
    assert 'runtimeOperationId' not in r['options'][0]


@pytest.mark.parametrize('defect', ['config', 'ready', 'attached', 'missing-route', 'missing-detach', 'ambiguous', 'drain', 'resources'])
def test_incomplete_materials_never_offer_a_command(setup, defect):
    if defect == 'config': setup.binding['config_ref'] = None
    if defect == 'ready': setup.binding.update(enabled=False, operation_fence=True)
    if defect == 'attached': setup.snapshot[0]['handlerKind'] = 'extension'
    if defect == 'missing-route': setup.snapshot.pop()
    if defect == 'missing-detach': setup.candidates = []
    if defect == 'ambiguous': setup.candidates *= 2
    if defect == 'drain': setup.drain = True
    if defect == 'resources': setup.resources = True
    r = prepare(setup)
    assert not r['ready'] and r['options'] == [] and r['reasons'] and r['executable'] is False
    assert setup.validated == []


def test_predecessor_permission_is_mandatory(setup):
    setup.denied = OLD
    with pytest.raises(PermissionError): prepare(setup)
    assert setup.validated == []


@pytest.mark.parametrize('defect', ['corrupt', 'group-version'])
def test_corrupt_or_drifted_exit_is_not_a_candidate(setup, defect):
    if defect == 'corrupt': setup.corrupt = True
    else: setup.candidates[0]['fenced_group_revision'] = 365
    with pytest.raises(ValueError): prepare(setup)
    assert setup.validated == []


def url():
    return f'/v1/bundle-runtime-installations/{TARGET}/ecommerce-growth-successor-registration-preparation'


def test_http_preparation_is_nonexecuting_and_not_cached():
    h = original_harness.__wrapped__()
    def read(**kw):
        from aos_api.ecommerce_growth_successor_preparation import SuccessorPreparation
        h.calls.append(kw)
        return SuccessorPreparation(schemaVersion='aos.ecommerce.successor-preparation/v1',
            tenant=dict(orgId='org-org', projectId='dev-project'), installationId=TARGET,
            ready=False, reasons=('新安装尚未完成运行配置',), options=(), executable=False)
    h.service.prepare_successor_registration = read
    r = h.client.get(url(), headers={'Idempotency-Key':'prepare-one'})
    assert r.status_code == 200, r.text
    assert r.headers['Cache-Control'] == 'no-store'
    assert r.json()['options'] == [] and r.json()['executable'] is False
    assert h.calls == [dict(scope=SCOPE, installation_id=TARGET, idempotency_key='prepare-one', actor='signed-user')]


def test_preparation_permission_error_does_not_disclose_source():
    h = original_harness.__wrapped__()
    def denied(**kw): raise PermissionError('private-sentinel '+OLD)
    h.service.prepare_successor_registration = denied
    r = h.client.get(url(), headers={'Idempotency-Key':'prepare-one'})
    assert r.status_code == 403 and OLD not in r.text and 'private-sentinel' not in r.text


def test_preparation_requires_original_key():
    h = original_harness.__wrapped__()
    h.service.prepare_successor_registration = lambda **kw:pytest.fail('must reject missing key')
    assert h.client.get(url()).status_code == 400

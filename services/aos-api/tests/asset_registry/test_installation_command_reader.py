"""Read-only command recovery through original receipt and authorization primitives."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

import psycopg
import pytest

from aos_api.asset_registry.composition_contracts import InstallationResponse
from aos_api.asset_registry.composition_store import PostgresCompositionStore
from aos_api.asset_registry.errors import IdempotencyConflictError, LockIntegrityCorruptError, MarkingAccessDeniedError
from aos_api.asset_registry import installation_command_reader as reader_module
from aos_api.asset_registry.installation_command_reader import ReadOnlyInstallationCommandReader
from aos_api.asset_registry.installation_service import InstallationService
from aos_api.asset_registry.installation_store import InstallationPersistenceError, PostgresInstallationStore

ORG, PROJECT, ACTOR = 'org-org', 'dev-project', 'synthetic-reader-author'
HASH = 'sha256:' + 'a' * 64
IID = '22222222-2222-4222-8222-222222222222'
CID = '11111111-1111-4111-8111-111111111111'


def response():
    now = datetime(2026, 10, 28, tzinfo=timezone.utc)
    return InstallationResponse.model_validate(dict(
        installationId=IID, displayName='Synthetic readonly receipt', state='draft',
        currentRevision=1, activeRevision=None, previousActiveRevision=None, etagVersion=1,
        createdAt=now, updatedAt=now,
        current=dict(installationId=IID, revision=1, parentRevision=None, state='draft',
            compositionId=CID, lockRevision=1, lockHash=HASH, permissionDiffHash=HASH,
            migrationPlanHash=HASH, contributionDiffHash=HASH, overlayRevision='synthetic',
            requestedBy=ACTOR, decisionId=None, createdAt=now), decision=None,
        events=[dict(sequence=1, fromRevision=None, toRevision=1, fromState=None,
            toState='draft', actor=ACTOR, reason=None, evidence=None, createdAt=now)]))


class ReadConnection:
    def __init__(self):
        self.mode = 'on'; self.row = None; self.calls = []
        self.scope = (ORG,PROJECT)
        self.commit = Mock(side_effect=AssertionError('read must not commit'))
        self.error = None

    def execute(self, sql, parameters=None):
        self.calls.append((sql, parameters))
        if 'transaction_read_only' in sql:
            return SimpleNamespace(fetchone=lambda: {'transaction_read_only': self.mode})
        if 'current_setting' in sql:
            return SimpleNamespace(fetchone=lambda: {'org_id':self.scope[0],'project_id':self.scope[1]})
        assert sql.lstrip().startswith('SELECT') and 'bundle_installation_command' in sql
        if self.error: raise self.error
        return SimpleNamespace(fetchone=lambda: deepcopy(self.row))


@pytest.fixture
def setup_reader():
    conn = ReadConnection(); opens = []
    @contextmanager
    def connect():
        opens.append(True); yield conn
    store = PostgresInstallationStore(connect)
    store.execute_idempotent = Mock(side_effect=AssertionError('no command execution'))
    compositions = PostgresCompositionStore(connect)
    target = SimpleNamespace(payload=SimpleNamespace(permission_diff=SimpleNamespace(target=SimpleNamespace(markings=[]))))
    compositions.get_lock = Mock(return_value=target)
    service = InstallationService(store=store, composition_store=compositions, revalidator=None)
    reader = ReadOnlyInstallationCommandReader(connect_factory=connect, installation_service=service)
    args = dict(org_id=ORG, project_id=PROJECT, operation='create', idempotency_key='synthetic-create',
        subject=ACTOR, request_hash=HASH, markings=[], current_check=lambda c: True)
    return SimpleNamespace(conn=conn, connect=connect, opens=opens, store=store,
        compositions=compositions, service=service, reader=reader, args=args, target=target)


def install_row(setup):
    setup.conn.row = dict(subject=ACTOR, request_hash=HASH, status_code=201,
        response_json=response().model_dump(mode='json', by_alias=True), response_etag='"1"')


def test_missing_returns_none_without_authorizer_or_command(setup_reader):
    s = setup_reader
    assert not s.opens
    assert s.reader.read(**s.args) is None
    s.store.execute_idempotent.assert_not_called(); s.conn.commit.assert_not_called()
    s.compositions.get_lock.assert_not_called()
    assert s.conn.calls[-1][1] == (ORG, PROJECT, 'create', 'synthetic-create')


def test_hit_uses_original_response_etag_and_lock_authorizer(setup_reader):
    s = setup_reader; install_row(s)
    receipt = s.reader.read(**s.args)
    assert receipt.response_json == s.conn.row['response_json'] and receipt.replayed is True
    s.compositions.get_lock.assert_called_once_with(org_id=ORG, project_id=PROJECT,
        composition_id=CID, revision=1)
    s.store.execute_idempotent.assert_not_called(); s.conn.commit.assert_not_called()


@pytest.mark.parametrize('field,wrong,error', [('subject','another-subject',LockIntegrityCorruptError),
    ('request_hash','sha256:'+'b'*64,IdempotencyConflictError)])
def test_other_subject_or_hash_never_returns_receipt(setup_reader,field,wrong,error):
    s = setup_reader; install_row(s); s.conn.row[field] = wrong
    with pytest.raises(error): s.reader.read(**s.args)
    s.compositions.get_lock.assert_not_called(); s.store.execute_idempotent.assert_not_called()


@pytest.mark.parametrize('mode', ['off',None,True,1])
def test_rw_or_unknown_transaction_refused_before_receipt_query(setup_reader,mode):
    s = setup_reader; s.conn.mode = mode
    with pytest.raises(PermissionError): s.reader.read(**s.args)
    assert len(s.conn.calls) == 1


@pytest.mark.parametrize('field,wrong', [('org_id',''),('project_id',None),('operation',' create'),
    ('idempotency_key','a'*161),('subject',' '),('request_hash','invalid'),('current_check',None)])
def test_invalid_input_refused_before_open(setup_reader,field,wrong):
    s = setup_reader; args = {**s.args,field:wrong}
    with pytest.raises((ValueError,TypeError)): s.reader.read(**args)
    assert not s.opens


@pytest.mark.parametrize('value',[False,None,1,object()])
def test_current_guard_requires_strict_true(setup_reader,value):
    s = setup_reader
    with pytest.raises(PermissionError): s.reader.read(**{**s.args,'current_check':lambda c:value})
    assert len(s.conn.calls) == 1


def test_guard_exception_is_not_missing_record(setup_reader):
    s = setup_reader
    def failure(conn): raise RuntimeError('current authority unavailable')
    with pytest.raises(RuntimeError): s.reader.read(**{**s.args,'current_check':failure})
    assert len(s.conn.calls) == 1


@pytest.mark.parametrize('kind',['coroutine','generator','async_generator'])
def test_lazy_guard_is_not_driven(setup_reader,kind):
    s = setup_reader; effects=[]
    async def coroutine(): effects.append('coroutine'); return True
    def generator(): effects.append('generator'); yield True
    async def async_generator(): effects.append('async_generator'); yield True
    lazy = {'coroutine':coroutine,'generator':generator,'async_generator':async_generator}[kind]()
    with pytest.raises(PermissionError): s.reader.read(**{**s.args,'current_check':lambda c:lazy})
    assert not effects and len(s.conn.calls) == 1
    if kind=='coroutine': assert lazy.cr_frame is None
    if kind=='generator': assert lazy.gi_frame is None


@pytest.mark.parametrize('mutation,error',[('bad_dto',LockIntegrityCorruptError),
    ('stale_etag',LockIntegrityCorruptError),('bad_etag',LockIntegrityCorruptError),
    ('bad_status',LockIntegrityCorruptError),('markings',MarkingAccessDeniedError)])
def test_original_receipt_and_authorizer_reject_corruption(setup_reader,mutation,error):
    s=setup_reader; install_row(s)
    if mutation=='bad_dto':s.conn.row['response_json']={'installationId':IID}
    if mutation=='stale_etag':s.conn.row['response_etag']='"2"'
    if mutation=='bad_etag':s.conn.row['response_etag']='weak'
    if mutation=='bad_status':s.conn.row['status_code']=True
    if mutation=='markings':s.target.payload.permission_diff.target.markings=['restricted']
    with pytest.raises(error):s.reader.read(**s.args)
    s.store.execute_idempotent.assert_not_called();s.conn.commit.assert_not_called()


def test_database_error_is_redacted_and_not_none(setup_reader):
    s=setup_reader;s.conn.error=psycopg.OperationalError('sensitive test detail')
    with pytest.raises(InstallationPersistenceError,match='installation persistence failed') as err:
        s.reader.read(**s.args)
    assert 'sensitive' not in str(err.value)


def test_cross_scope_uses_explicit_original_query_binding(setup_reader):
    s=setup_reader
    s.conn.scope=('dev-org',PROJECT)
    assert s.reader.read(**{**s.args,'org_id':'dev-org'}) is None
    assert s.conn.calls[-1][1] == ('dev-org',PROJECT,'create','synthetic-create')


def test_factory_and_authorizer_drift_refused_before_open(setup_reader):
    s=setup_reader;s.compositions._connect_factory=lambda:None
    with pytest.raises(ValueError):s.reader.read(**s.args)
    assert not s.opens
    s.compositions._connect_factory=s.connect
    s.service._authorize_receipt=lambda *a,**k:True
    with pytest.raises(ValueError):s.reader.read(**s.args)
    assert not s.opens


def test_no_default_or_nonoriginal_service(setup_reader):
    s=setup_reader
    with pytest.raises(TypeError):ReadOnlyInstallationCommandReader()
    with pytest.raises(ValueError):ReadOnlyInstallationCommandReader(connect_factory=s.connect,installation_service=object())


def test_original_tenant_helper_is_delegated(setup_reader):
    s=setup_reader
    with patch.object(reader_module,'apply_asset_transaction_scope', wraps=reader_module.apply_asset_transaction_scope) as scope:
        assert s.reader.read(**s.args) is None
    scope.assert_called_once_with(s.conn,org_id=ORG,project_id=PROJECT)


def test_guard_revocation_of_binding_blocks_before_lookup(setup_reader):
    s=setup_reader
    def revoke(conn):s.service._store._connect_factory=lambda:None;return True
    with pytest.raises(ValueError):s.reader.read(**{**s.args,'current_check':revoke})
    assert len(s.conn.calls)==1


@pytest.mark.parametrize('kind',['coroutine','generator','async_generator'])
def test_declared_async_guard_refused_before_open(setup_reader,kind):
    s=setup_reader
    async def coroutine(conn):return True
    def generator(conn):yield True
    async def async_generator(conn):yield True
    guard={'coroutine':coroutine,'generator':generator,'async_generator':async_generator}[kind]
    with pytest.raises(ValueError):s.reader.read(**{**s.args,'current_check':guard})
    assert not s.opens


def test_pending_future_is_cancelled_without_driving_loop(setup_reader):
    import asyncio
    s=setup_reader;loop=SimpleNamespace(get_debug=lambda:False)
    future=asyncio.Future(loop=loop)
    with pytest.raises(PermissionError):s.reader.read(**{**s.args,'current_check':lambda conn:future})
    assert future.cancelled() and len(s.conn.calls)==1


def test_guard_cannot_turn_readonly_transaction_into_rw(setup_reader):
    s=setup_reader
    def changed(conn):conn.mode='off';return True
    with pytest.raises(PermissionError):s.reader.read(**{**s.args,'current_check':changed})
    assert all('bundle_installation_command' not in sql for sql,unused in s.conn.calls)


def test_guard_cannot_rebind_transaction_to_another_tenant(setup_reader):
    s=setup_reader
    def changed(conn):conn.scope=('dev-org',PROJECT);return True
    with pytest.raises(PermissionError):s.reader.read(**{**s.args,'current_check':changed})
    assert all('bundle_installation_command' not in sql for sql,unused in s.conn.calls)

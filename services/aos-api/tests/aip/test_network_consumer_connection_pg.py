"""Real disposable PG identity checks; never formal credential proof."""
from contextlib import contextmanager
import pytest
from aos_api.aip_network_consumer_connection import ConsumerDatabaseBlocked, require_consumer_identity
from tests.aip.test_network_consumer_boundary_pg import isolated_owner, SCOPE


@contextmanager
def caller(mutation=None):
    with isolated_owner() as conn:
        database = conn.info.dbname
        conn.execute('ALTER ROLE aos_network_consumer_call LOGIN')
        if mutation:
            conn.execute(mutation)
        conn.execute('SET SESSION AUTHORIZATION aos_network_consumer_call')
        conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", SCOPE.key)
        try:
            yield conn, database
        finally:
            conn.rollback()


def test_exact_connection_preflight_is_read_only():
    with caller() as (conn, database):
        conn.execute('SET TRANSACTION READ ONLY')
        require_consumer_identity(conn, SCOPE, database)
        assert conn.execute('SHOW transaction_read_only').fetchone()['transaction_read_only'] == 'on'


@pytest.mark.parametrize('case', ['database', 'scope', 'runtime'])
def test_wrong_connection_identity_rejected(case):
    with caller() as (conn, database):
        if case == 'scope':
            conn.execute("SELECT set_config('aos.org_id','other-org',true)")
        if case == 'runtime':
            conn.execute('RESET SESSION AUTHORIZATION')
            conn.execute('SET SESSION AUTHORIZATION aos_runtime')
        with pytest.raises(ConsumerDatabaseBlocked):
            require_consumer_identity(conn, SCOPE, 'wrong_database' if case == 'database' else database)


@pytest.mark.parametrize('mutation', [
    'ALTER ROLE aos_network_consumer_call BYPASSRLS',
    'ALTER ROLE aos_network_consumer_owner LOGIN',
    'GRANT aos_runtime TO aos_network_consumer_call',
    'GRANT SELECT (receipt_id) ON aip_network_policy_receipt TO aos_network_consumer_call',
    'ALTER FUNCTION aip_consume_network_activation_a0v_120(text,text,text,text) SECURITY INVOKER',
    'REVOKE EXECUTE ON FUNCTION aip_consume_network_activation_a0v_120(text,text,text,text) FROM aos_network_consumer_call',
])
def test_role_acl_and_function_drift_rejected(mutation):
    with caller(mutation) as (conn, database):
        with pytest.raises(ConsumerDatabaseBlocked):
            require_consumer_identity(conn, SCOPE, database)


@pytest.fixture
def private_passfile(tmp_path):
    folder = tmp_path / 'consumer'
    folder.mkdir(mode=0o700)
    path = folder / 'pgpass'
    path.write_text('# isolated fixture, no credentials\n')
    path.chmod(0o600)
    return path


@pytest.mark.parametrize('case', ['remote', 'port', 'database', 'relative', 'mode', 'symlink'])
def test_consumer_config_rejects_unsafe_target_or_file(private_passfile, case):
    from aos_api.aip_network_consumer_connection import ConsumerDatabaseConfig
    path = private_passfile
    if case == 'mode':
        path.chmod(0o644)
    if case == 'symlink':
        link = path.parent / 'link'
        link.symlink_to(path)
        path = link
    with pytest.raises(ConsumerDatabaseBlocked):
        ConsumerDatabaseConfig('remote.example' if case == 'remote' else '127.0.0.1',
                               True if case == 'port' else 5433,
                               'bad database' if case == 'database' else 'isolated_test',
                               'relative' if case == 'relative' else path)


def test_connection_revalidates_file_before_network(private_passfile):
    from aos_api.aip_network_consumer_connection import ConsumerDatabaseConfig, connect_consumer
    config = ConsumerDatabaseConfig('127.0.0.1', 1, 'isolated_test', private_passfile)
    private_passfile.chmod(0o644)
    with pytest.raises(ConsumerDatabaseBlocked, match='PRIVATE_CREDENTIAL_REQUIRED'):
        with connect_consumer(config, SCOPE):
            pytest.fail('unsafe credential was accepted')


def test_connection_rejects_ambient_override_before_network(private_passfile, monkeypatch):
    from aos_api.aip_network_consumer_connection import ConsumerDatabaseConfig, connect_consumer
    config = ConsumerDatabaseConfig('127.0.0.1', 1, 'isolated_test', private_passfile)
    monkeypatch.setenv('PGOPTIONS', '-c search_path=public')
    with pytest.raises(ConsumerDatabaseBlocked, match='EXACT_CONNECTION_REQUIRED'):
        with connect_consumer(config, SCOPE):
            pytest.fail('ambient override was accepted')


@contextmanager
def live_test_config(private_passfile):
    import secrets
    from psycopg import sql
    from aos_api.aip_network_consumer_connection import ConsumerDatabaseConfig
    with isolated_owner() as admin:
        admin.execute("SELECT pg_advisory_lock(hashtext('bg00ek-caller-login-test'))")
        original = admin.execute("SELECT rolcanlogin,rolpassword IS NULL AS no_password FROM pg_authid "
                                 "WHERE rolname='aos_network_consumer_call'").fetchone()
        assert original == {'rolcanlogin': False, 'no_password': True}
        password = secrets.token_urlsafe(32)
        admin.execute(sql.SQL('ALTER ROLE aos_network_consumer_call LOGIN PASSWORD {}').format(sql.Literal(password)))
        admin.commit()
        try:
            host, port, database = admin.info.host, admin.info.port, admin.info.dbname
            private_passfile.write_text(f'{host}:{port}:{database}:aos_network_consumer_call:{password}\n')
            yield ConsumerDatabaseConfig(host, port, database, private_passfile)
        finally:
            admin.execute('ALTER ROLE aos_network_consumer_call NOLOGIN PASSWORD NULL')
            admin.commit()
            private_passfile.write_text('# removed temporary test credential\n')
            admin.execute("SELECT pg_advisory_unlock(hashtext('bg00ek-caller-login-test'))")


def test_real_connection_factory_scope_and_atomic_consumption(private_passfile):
    from aos_api.aip_network_consumer_connection import connect_consumer
    from tests.aip.test_network_atomic_consumer_pg import _approved, consume, counts
    proposal, event, _, _ = _approved(None)
    with live_test_config(private_passfile) as config:
        with connect_consumer(config, SCOPE, read_only=True) as conn:
            identity = conn.execute('SELECT session_user AS login,current_user AS role').fetchone()
            assert identity == {'login': 'aos_network_consumer_call', 'role': 'aos_network_consumer_call'}
            assert conn.read_only is True
        assert conn.closed
        with connect_consumer(config, SCOPE) as conn:
            receipt = consume(conn, proposal, event)
        assert conn.closed and counts(proposal) == (1, 1, 1)
        with connect_consumer(config, SCOPE) as conn:
            assert consume(conn, proposal, event) == receipt
        assert counts(proposal) == (1, 1, 1)


def test_factory_rolls_back_and_does_not_reuse_scope_after_commit(private_passfile):
    from aos_api.aip_network_consumer_connection import connect_consumer
    from tests.aip.test_network_atomic_consumer_pg import _approved, consume, counts
    proposal, event, _, _ = _approved(None)
    with live_test_config(private_passfile) as config:
        with pytest.raises(ConsumerDatabaseBlocked, match='TRANSACTION_FAILED_RECONCILE_REQUIRED'):
            with connect_consumer(config, SCOPE) as conn:
                consume(conn, proposal, event)
                conn.execute('SELECT 1/0')
        assert conn.closed and counts(proposal) == (0, 0, 0)
        with connect_consumer(config, SCOPE) as conn:
            conn.commit()
            with pytest.raises(ConsumerDatabaseBlocked, match='DATABASE_IDENTITY_REQUIRED'):
                require_consumer_identity(conn, SCOPE, config.database)
        with connect_consumer(config, SCOPE) as conn:
            consume(conn, proposal, event)
        assert counts(proposal) == (1, 1, 1)


def test_real_factory_consumes_approved_successor_revision(private_passfile):
    import uuid
    from aos_api.aip_network_consumer_connection import connect_consumer
    from aos_api.aip_network_policy_action_producer import propose_network_activation, decide_network_activation
    from aos_api.aip_network_policy_contracts import NetworkPolicyRevisionCreate
    from aos_api.aip_action_models import DecideActionProposalRequest
    from aos_api.auth import Principal
    from tests.aip.test_network_atomic_consumer_pg import _approved, consume, counts
    from tests.aip.test_network_approval_precheck_expiry_pg import isolated_issuer
    proposal, event, checker, _ = _approved(None)
    with live_test_config(private_passfile) as config:
        with connect_consumer(config, SCOPE) as conn:
            first = consume(conn, proposal, event)
        with isolated_owner() as conn:
            row = conn.execute('SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s',
                               (*SCOPE.key, proposal)).fetchone()
        candidate = NetworkPolicyRevisionCreate.model_validate({**row['payload']['candidate'], 'revision': 2})
        maker = Principal(subject=row['created_by'], org_id=SCOPE.org_id, project_id=SCOPE.project_id,
                          roles=['owner'], token_kind='oidc')
        next_proposal = propose_network_activation(maker, candidate, expected_version=1,
                                                   idempotency_key=uuid.uuid4().hex, expires_at=row['expires_at'])
        approver = Principal(subject=checker, org_id=SCOPE.org_id, project_id=SCOPE.project_id,
                             roles=['admin'], token_kind='oidc')
        approved = decide_network_activation(approver, next_proposal.proposal.id, uuid.uuid4().hex,
            DecideActionProposalRequest.model_validate({
                'expectedProposalVersion': next_proposal.proposal.version,
                'expectedProposalHash': next_proposal.proposal.proposal_hash,
                'decision': 'approved', 'reason': 'isolated successor proof',
                'approvalExpiresAt': row['expires_at'].isoformat(),
            }), connect_factory=isolated_issuer)
        with connect_consumer(config, SCOPE) as conn:
            second = consume(conn, approved.proposal.id, approved.approvals[0].id)
        assert second['resourceId'] == first['resourceId'] and second['revision'] == 2
        assert counts(approved.proposal.id) == (1, 2, 1)
        with connect_consumer(config, SCOPE) as conn:
            assert consume(conn, proposal, event) == first
        with isolated_owner() as conn:
            head = conn.execute('SELECT current_revision,version FROM aip_network_policy_head '
                                'WHERE org_id=%s AND project_id=%s AND policy_id=%s',
                                (*SCOPE.key, first['resourceId'])).fetchone()
            assert head == {'current_revision': 2, 'version': 2}


def test_expiry_after_receipt_insert_rolls_back_entire_consumption(private_passfile):
    import time
    import uuid
    import psycopg
    from psycopg import sql
    from concurrent.futures import ThreadPoolExecutor
    from aos_api.aip_network_consumer_connection import connect_consumer
    from tests.aip.test_network_atomic_consumer_pg import _approved, consume, counts
    suffix = uuid.uuid4().hex[:12]
    function_name, trigger_name = 'bg00ek_wait_' + suffix, 'bg00ek_wait_' + suffix
    application = 'bg00ek-final-' + suffix
    lock_key = int(suffix[:7], 16)
    with live_test_config(private_passfile) as config:
        proposal, event, _, expires = _approved('approval')
        with isolated_owner() as blocker:
            blocker.execute(sql.SQL('''CREATE FUNCTION public.{}() RETURNS trigger LANGUAGE plpgsql
                SET search_path=pg_catalog AS $$ BEGIN
                IF NEW.idempotency_key={} AND NEW.operation='network_policy.activate' THEN
                    PERFORM pg_advisory_xact_lock({});
                END IF; RETURN NEW; END $$''').format(
                    sql.Identifier(function_name), sql.Literal(proposal), sql.Literal(lock_key)))
            blocker.execute(sql.SQL('CREATE TRIGGER {} AFTER INSERT ON aip_network_policy_receipt '
                                    'FOR EACH ROW EXECUTE FUNCTION public.{}()').format(
                                        sql.Identifier(trigger_name), sql.Identifier(function_name)))
            blocker.execute('SELECT pg_advisory_lock(%s)', (lock_key,))
            blocker.commit()
            try:
                def attempt():
                    with connect_consumer(config, SCOPE) as conn:
                        conn.execute("SELECT set_config('application_name',%s,true)", (application,))
                        with pytest.raises(psycopg.errors.InsufficientPrivilege, match='NETWORK_CONSUMER_EXPIRED'):
                            consume(conn, proposal, event)
                        conn.rollback()
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(attempt)
                    try:
                        deadline = time.monotonic() + 3
                        while time.monotonic() < deadline:
                            blocker.execute('SELECT pg_stat_clear_snapshot()')
                            waiting = blocker.execute('SELECT wait_event FROM pg_stat_activity WHERE application_name=%s',
                                                      (application,)).fetchone()
                            if waiting and waiting['wait_event'] == 'advisory':
                                break
                            time.sleep(.02)
                        else:
                            raise AssertionError('receipt AFTER INSERT wait not reached')
                        now = blocker.execute('SELECT clock_timestamp() AS now').fetchone()['now']
                        assert now < expires
                        blocker.execute('SELECT pg_sleep(%s)', ((expires-now).total_seconds()+.05,))
                    finally:
                        blocker.execute('SELECT pg_advisory_unlock(%s)', (lock_key,))
                    future.result(timeout=12)
            finally:
                blocker.rollback()
                blocker.execute('SELECT pg_advisory_unlock(%s)', (lock_key,))
                blocker.execute(sql.SQL('DROP TRIGGER {} ON aip_network_policy_receipt').format(sql.Identifier(trigger_name)))
                blocker.execute(sql.SQL('DROP FUNCTION public.{}()').format(sql.Identifier(function_name)))
                blocker.commit()
        assert counts(proposal) == (0, 0, 0)

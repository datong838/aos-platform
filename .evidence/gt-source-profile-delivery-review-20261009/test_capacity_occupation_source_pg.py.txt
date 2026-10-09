"""Real Source -> separate native business session; no execution grant."""
import secrets
import time
from threading import Event, Thread
from uuid import uuid4

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
from aos_api.aip_provider_capacity_source_contracts import ProviderCapacityConsumptionCommand
from aos_api.aip_provider_capacity_source_consumer import (
    ProviderCapacityConsumptionBlocked, consume_current_capacity_source,
)
from aos_api.aip_provider_capacity_publication_contracts import PublishedProviderCapacitySourceV2, parse_signed_capacity_body
from aos_api.db import get_dsn
from aos_api.tenant_scope import TenantScope, apply_transaction_scope
from tests.aip._runtime_guard_history_fixture import isolated_owner

pytest_plugins = ('tests.aip.test_capacity_source_publication_transaction_pg',)
SCOPE = TenantScope('org-org', 'dev-project')
ROLE = 'aos_provider_capacity_occupation'


def _assert_occupation_independent_owner(caller, source, command, sign, maker, material):
    from aos_api.aip_provider_capacity_occupation_source import consume_capacity_source_for_occupation
    from tests.aip.test_capacity_source_publication_transaction_pg import (
        _private_source_row_fingerprint, _integrated_signed_origin_withdrawal,
    )
    independent = 'occupation-owner-'+uuid4().hex
    with isolated_owner() as admin:
        admin.execute("INSERT INTO public.meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,%s,'owner')",(*SCOPE.key,independent))
        before = _private_source_row_fingerprint(admin)
    def current_read(item=None):
        caller.execute("SET LOCAL TimeZone='UTC'")
        apply_transaction_scope(caller,SCOPE)
        return consume_capacity_source_for_occupation(caller,item or command.model_copy(update={'bearer_token':sign(independent)}))
    assert independent!=maker and current_read()==source
    caller.rollback()
    for subject,role in [(independent,'viewer'),(independent,'editor'),(maker,'viewer')]:
        with isolated_owner() as admin:
            assert admin.execute('SELECT role FROM public.meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',(*SCOPE.key,subject)).fetchone()['role']=='owner'
            admin.execute('UPDATE public.meta_membership SET role=%s WHERE org_id=%s AND project_id=%s AND subject=%s',(role,*SCOPE.key,subject))
        try:
            with pytest.raises(ProviderCapacityConsumptionBlocked) as rejected:
                current_read()
            underlying = rejected.value.__context__
            if subject==maker:
                assert isinstance(underlying,psycopg.errors.NoDataFound)
                assert 'public.read_capacity_source_for_occupation(bytea,jsonb)' in underlying.diag.context
            else:
                assert isinstance(underlying,psycopg.errors.InvalidParameterValue)
                assert underlying.diag.message_primary=='CAPACITY_ORIGINAL_OWNER_REQUIRED'
        finally:
            caller.rollback()
            with isolated_owner() as admin:
                admin.execute("UPDATE public.meta_membership SET role='owner' WHERE org_id=%s AND project_id=%s AND subject=%s",(*SCOPE.key,subject))
        assert current_read()==source
        caller.rollback()
    tokens = ['invalid-consumer-jwt',sign(independent,wrong_key=True),sign(independent,changes={'exp':int(time.time())-1}),
              sign(independent,changes={'org_id':'dev-org'}),sign('unregistered-occupation-'+uuid4().hex),
              sign(independent,changes={'aud':'other-audience'}),sign(independent,changes={'iss':'https://wrong.example.test'}),
              sign(independent,changes={'project_id':'wrong-project'})]
    for token in tokens:
        try:
            with pytest.raises(ProviderCapacityConsumptionBlocked):
                current_read(command.model_copy(update={'bearer_token':token}))
        finally:caller.rollback()
    for changes in [{'asset_type':'ProviderCapacityRequest'},{'revision':True},{'revision':2},
                    {'content_hash':'0'*64},{'asset_id':'missing-occupation-source'}]:
        try:
            with pytest.raises(ProviderCapacityConsumptionBlocked):
                current_read(command.model_copy(update={'source_ref':command.source_ref.model_copy(update=changes),'bearer_token':sign(independent)}))
        finally:caller.rollback()
    with isolated_owner() as admin:
        admin.execute('GRANT aos_runtime TO '+ROLE+' WITH SET FALSE')
    try:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            apply_transaction_scope(caller,SCOPE)
    finally:
        caller.rollback()
        with isolated_owner() as admin:
            admin.execute('GRANT aos_runtime TO '+ROLE+' WITH SET TRUE')
    assert current_read()==source
    caller.rollback()
    withdrawal,signature,digest = _integrated_signed_origin_withdrawal(material)
    entered = Event(); finished = Event(); outcome = {}
    def withdrawn_snapshot_reader():
        try:
            caller.execute("SET LOCAL statement_timeout='8s'")
            caller.execute("SET LOCAL TimeZone='UTC'")
            apply_transaction_scope(caller,SCOPE)
            outcome['pid'] = caller.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
            entered.set()
            outcome['result'] = consume_capacity_source_for_occupation(caller,command.model_copy(update={'bearer_token':sign(independent)}))
        except BaseException as error:
            outcome['error'] = error
        finally:finished.set()
    with isolated_owner() as publisher:
        publisher.execute("SELECT set_config('aos.org_id',%s,false),set_config('aos.project_id',%s,false)",SCOPE.key)
        publisher.execute('SET SESSION AUTHORIZATION aos_provider_capacity_policy_publisher')
        publisher.commit()
        publisher_pid = publisher.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
        assert publisher.execute('SELECT aos_capacity_publication_private.withdraw_origin(%s,%s) AS digest',(withdrawal,signature)).fetchone()['digest']==digest
        thread = Thread(target=withdrawn_snapshot_reader)
        try:
            thread.start()
            assert entered.wait(2)
            blocked = False
            deadline = time.monotonic()+2
            with isolated_owner() as observer:
                while time.monotonic()<deadline:
                    blocked = publisher_pid in observer.execute('SELECT pg_blocking_pids(%s) AS pids',(outcome['pid'],)).fetchone()['pids']
                    if blocked:break
                    time.sleep(0.02)
            assert blocked and not finished.is_set()
            publisher.commit()
            assert finished.wait(3)
            assert 'result' not in outcome and isinstance(outcome.get('error'),ProviderCapacityConsumptionBlocked)
            assert isinstance(outcome['error'].__context__,psycopg.errors.SerializationFailure)
            print('occupation signed_origin_writer_first native_blocked old_snapshot_rejected_40001')
        finally:
            publisher.rollback()
            thread.join(timeout=9)
            assert not thread.is_alive()
            caller.rollback()
    try:
        with pytest.raises(ProviderCapacityConsumptionBlocked) as rejected:
            current_read()
        underlying = rejected.value.__context__
        assert isinstance(underlying,psycopg.errors.NoDataFound)
        assert 'public.read_capacity_source_for_occupation(bytea,jsonb)' in underlying.diag.context
        print('occupation signed withdrawal native reason',underlying.diag.message_primary)
    finally:caller.rollback()
    with isolated_owner() as admin:
        assert admin.execute('SELECT epoch,head_origin_hash FROM aos_capacity_publication_private.registry_epoch').fetchone()==dict(epoch=2,head_origin_hash=None)
        row = admin.execute('SELECT raw_body,signature,prior_epoch,new_epoch FROM aos_capacity_publication_private.origin_withdrawal').fetchone()
        assert bytes(row['raw_body'])==withdrawal and bytes(row['signature'])==signature
        assert row['prior_epoch']==1 and row['new_epoch']==2
        assert _private_source_row_fingerprint(admin)==before
    print('occupation independent_owner three_current_owner_denials eight_auth_five_ref_denials native_set_denial signed_origin_withdrawn source_history_unchanged')


def _assert_occupation_epoch_concurrency(caller, source, command, sign, subject):
    from aos_api.aip_provider_capacity_occupation_source import consume_capacity_source_for_occupation
    with isolated_owner() as admin:
        allocation = admin.execute('SELECT proposal_id FROM public.aip_action_approval_event WHERE org_id=%s AND project_id=%s AND approval_event_id=%s',
            (*SCOPE.key,source.allocation_approval_ref.asset_id)).fetchone()['proposal_id']
    targets = [('aip_capacity_evidence_epoch','bundle_id',source.evidence_refs[0].asset_id),
               ('aip_capacity_withdrawal_epoch','proposal_id',source.source_proposal_ref.asset_id),
               ('aip_capacity_withdrawal_epoch','proposal_id',allocation)]
    caller.execute("SET LOCAL TimeZone='UTC'")
    apply_transaction_scope(caller,SCOPE)
    identity = caller.execute('SELECT pg_backend_pid() AS pid,pg_current_xact_id()::text AS xid').fetchone()
    assert consume_capacity_source_for_occupation(caller,command.model_copy(update={'bearer_token':sign(subject)})) == source
    assert caller.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid'] == identity['xid']
    started = [Event() for _ in targets]; done = [Event() for _ in targets]
    pids = {}; errors = {}; threads = []
    def writer(index,target):
        try:
            with isolated_owner() as admin:
                admin.execute("SET LOCAL statement_timeout='8s'")
                pids[index] = admin.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
                started[index].set()
                changed = admin.execute(psycopg.sql.SQL('UPDATE public.{} SET epoch=epoch WHERE org_id=%s AND project_id=%s AND {}=%s')
                    .format(psycopg.sql.Identifier(target[0]),psycopg.sql.Identifier(target[1])),(*SCOPE.key,target[2]))
                assert changed.rowcount == 1
        except BaseException as error:
            errors[index] = error
        finally:
            done[index].set()
    try:
        for index,target in enumerate(targets):
            thread = Thread(target=writer,args=(index,target));threads.append(thread);thread.start()
        assert all(e.wait(2) for e in started), errors
        deadline = time.monotonic()+2
        with isolated_owner() as observer:
            while time.monotonic()<deadline:
                blocked = {i for i,pid in pids.items() if identity['pid'] in observer.execute('SELECT pg_blocking_pids(%s) AS pids',(pid,)).fetchone()['pids']}
                if len(blocked)==3:break
                time.sleep(0.02)
        assert blocked=={0,1,2} and not any(e.is_set() for e in done), errors
        caller.commit()
        assert all(e.wait(3) for e in done) and not errors, errors
        print('occupation concurrency reader_first three_native_writers_blocked caller_commit_released same_xid')
    finally:
        caller.rollback()
        for thread in threads:thread.join(timeout=9)
    target = targets[0]
    entered = Event();finished = Event();outcome = {}
    expiry = int(time.time())+3
    expiring = command.model_copy(update={'bearer_token':sign(subject,changes={'exp':expiry})})
    def reader():
        try:
            caller.execute("SET LOCAL statement_timeout='8s'")
            caller.execute("SET LOCAL TimeZone='UTC'")
            apply_transaction_scope(caller,SCOPE)
            outcome['pid'] = caller.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
            entered.set()
            outcome['result'] = consume_capacity_source_for_occupation(caller,expiring)
        except BaseException as error:
            outcome['error'] = error
        finally:
            finished.set()
    with isolated_owner() as admin:
        writer_pid = admin.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
        assert admin.execute(psycopg.sql.SQL('SELECT epoch FROM public.{} WHERE org_id=%s AND project_id=%s AND {}=%s FOR UPDATE')
            .format(psycopg.sql.Identifier(target[0]),psycopg.sql.Identifier(target[1])),(*SCOPE.key,target[2])).fetchone()['epoch'] == 0
        thread = Thread(target=reader)
        try:
            thread.start()
            assert entered.wait(2), outcome.keys()
            deadline = time.monotonic()+2
            blocked = False
            with isolated_owner() as observer:
                while time.monotonic()<deadline:
                    blocked = writer_pid in observer.execute('SELECT pg_blocking_pids(%s) AS pids',(outcome['pid'],)).fetchone()['pids']
                    if blocked:break
                    time.sleep(0.02)
            assert blocked and not finished.is_set()
            assert time.time()<expiry
            while time.time()<expiry+0.1:time.sleep(0.02)
            admin.commit()
            assert finished.wait(3)
            assert 'result' not in outcome and isinstance(outcome.get('error'),ProviderCapacityConsumptionBlocked)
            underlying = outcome['error'].__context__
            assert isinstance(underlying,psycopg.errors.InvalidParameterValue)
            assert underlying.diag.message_primary == 'CAPACITY_CURRENT_SOURCE_EXPIRED'
            print('occupation concurrency writer_first native_wait actual_jwt_expired source_rejected_22023')
        finally:
            admin.rollback()
            thread.join(timeout=9)
            assert not thread.is_alive()
            caller.rollback()
    caller.execute("SET LOCAL TimeZone='UTC'")
    apply_transaction_scope(caller,SCOPE)
    assert consume_capacity_source_for_occupation(caller,command.model_copy(update={'bearer_token':sign(subject)})) == source
    caller.rollback()
    with isolated_owner() as admin:
        for table,column,asset in targets:
            assert admin.execute(psycopg.sql.SQL('SELECT epoch FROM public.{} WHERE org_id=%s AND project_id=%s AND {}=%s')
                .format(psycopg.sql.Identifier(table),psycopg.sql.Identifier(column)),(*SCOPE.key,asset)).fetchone()['epoch'] == 0


def test_occupation_reader_does_not_call_issuer_only_epoch_lock():
    """The native occupation session cannot satisfy the legacy issuer lock."""
    from aos_api.aip_provider_capacity_occupation_source import occupation_source_statements
    reader = occupation_source_statements()[0]
    assert 'public.aos_capacity_evidence_epoch_issuer_lock(' not in reader, (
        'Occupation facts must use an audited purpose lock; SECURITY DEFINER '
        'does not change the original issuer-only session_user requirement'
    )


@pytest.mark.parametrize('native_original_fact_reader', ['shared','distinct'], indirect=True)
def test_occupation_source_consumption_uses_actual_business_caller(exact_public_source_caller, https_signer):
    sign, _ = https_signer
    issuer, packet, material, original = exact_public_source_caller
    issuance, _, _ = material['actual_command']()
    asset = 'occupation-source-' + uuid4().hex
    pending = issuer.execute('SELECT * FROM public.prepare_capacity_source(%s,%s,%s,%s::jsonb)',
        (packet, issuance.idempotency_key, asset, Jsonb(material['refs'][-1]))).fetchone()
    raw = bytes(pending['source_raw'])
    finalized = issuer.execute('SELECT * FROM public.commit_capacity_source(%s,%s,%s)',
        (issuance.idempotency_key, raw, material['source_key'].sign(raw))).fetchone()
    issuer.commit()
    source = parse_signed_capacity_body(raw, PublishedProviderCapacitySourceV2)
    exact = FormalExactRef(asset_type='ProviderCapacitySourceRevision', asset_id=asset,
        revision=1, content_hash=finalized['content_hash'])
    command = ProviderCapacityConsumptionCommand(schema_version=1, tenant=source.tenant, source_ref=exact,
        bearer_token=sign(original[0]['maker']))
    password = secrets.token_urlsafe(32)
    with isolated_owner() as admin:
        prior = admin.execute("""SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,
            rolreplication,rolbypassrls,shobj_description(oid,'pg_authid') AS description
            FROM pg_roles WHERE rolname=%s""", (ROLE,)).fetchone()
        label = 'Owned isolated GT capacity occupation Source fixture; never formal identity'
        if prior is None:
            admin.execute("CREATE ROLE aos_provider_capacity_occupation NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS")
            admin.execute(psycopg.sql.SQL('COMMENT ON ROLE aos_provider_capacity_occupation IS {}').format(psycopg.sql.Literal(label)))
        else:
            assert prior['description'] == label
            assert all(prior[k] is False for k in prior.keys() - {'description'})
            assert admin.execute("SELECT 1 FROM pg_auth_members WHERE roleid=%s::regrole OR member=%s::regrole", (ROLE,ROLE)).fetchone() is None
        admin.execute("SET LOCAL password_encryption='scram-sha-256'")
        admin.execute(psycopg.sql.SQL('ALTER ROLE aos_provider_capacity_occupation LOGIN PASSWORD {}').format(psycopg.sql.Literal(password)))
        admin.execute('GRANT aos_runtime TO aos_provider_capacity_occupation')
        runtime = admin.execute("SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname='aos_runtime'").fetchone()
        assert runtime and not any(runtime.values())
    try:
        from aos_api.aip_provider_capacity_occupation_source import occupation_source_statements
        from aos_api.aip_provider_capacity_occupation_epoch_profile import occupation_epoch_profile_statements
        with isolated_owner() as admin:
            for statement in occupation_epoch_profile_statements():
                admin.execute(statement)
            for statement in occupation_source_statements():
                admin.execute(statement)
        params = conninfo_to_dict(get_dsn())
        params.update(user=ROLE, password=password, require_auth='scram-sha-256')
        with psycopg.connect(**params, row_factory=dict_row) as caller:
            caller.isolation_level = psycopg.IsolationLevel.SERIALIZABLE
            caller.execute("SET LOCAL TimeZone='UTC'")
            apply_transaction_scope(caller, SCOPE)
            identity = caller.execute('SELECT session_user AS login,current_user AS role,pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
            assert caller.pgconn.used_password
            assert identity['login'] == ROLE and identity['role'] == 'aos_runtime'
            assert identity['xid'] != source.issuance_context.transaction_id
            assert identity['pid'] != source.issuance_context.backend_pid
            caller.execute('SAVEPOINT old_interface_denial')
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                caller.execute('SELECT * FROM public.read_current_capacity_source(%s,%s::jsonb)',
                    (b'{}', Jsonb(exact.model_dump(mode='json',by_alias=True))))
            caller.execute('ROLLBACK TO SAVEPOINT old_interface_denial')
            with pytest.raises(ProviderCapacityConsumptionBlocked):
                consume_current_capacity_source(caller, command)
            from aos_api.aip_provider_capacity_occupation_source import consume_capacity_source_for_occupation
            try:
                result = consume_capacity_source_for_occupation(caller, command)
            except ProviderCapacityConsumptionBlocked as error:
                underlying = error.__context__
                print('occupation diagnostic', type(underlying).__name__,
                    underlying.diag.message_primary if isinstance(underlying,psycopg.Error) else str(underlying))
                raise
            assert type(result) is PublishedProviderCapacitySourceV2
            assert result.model_dump(mode='json',by_alias=True) == source.model_dump(mode='json',by_alias=True)
            assert result.execution_allowed is False
            mutated_commands = [
                command.model_copy(update={'unexpected_execution_allowed': True}),
                command.model_copy(update={'source_ref': command.source_ref.model_copy(
                    update={'unexpected_execution_allowed': True})}),
                command.model_copy(update={'tenant': command.tenant.model_copy(
                    update={'unexpected_execution_allowed': True})}),
            ]
            for mutated in mutated_commands:
                with pytest.raises(ProviderCapacityConsumptionBlocked,
                                   match='^CAPACITY_OCCUPATION_SOURCE_REQUIRED$'):
                    consume_capacity_source_for_occupation(caller, mutated)
            assert consume_capacity_source_for_occupation(caller, command) == source
            assert caller.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid'] == identity['xid']
            caller.rollback()
            # Each committed fault must be visible to a fresh caller snapshot.
            database = psycopg.sql.Identifier(caller.info.dbname)
            with isolated_owner() as admin:
                admin.execute(psycopg.sql.SQL('GRANT CONNECT ON DATABASE {} TO '+ROLE).format(database))
            caller.execute("SET LOCAL TimeZone='UTC'")
            apply_transaction_scope(caller, SCOPE)
            connected = command.model_copy(update={'bearer_token':sign(original[0]['maker'])})
            assert consume_capacity_source_for_occupation(caller, connected) == source
            caller.rollback()
            faults = [
                ('table_select', 'GRANT SELECT ON public.twa_org TO '+ROLE, 'REVOKE SELECT ON public.twa_org FROM '+ROLE),
                ('column_select', 'GRANT SELECT(name) ON public.meta_object_type TO '+ROLE, 'REVOKE SELECT(name) ON public.meta_object_type FROM '+ROLE),
                ('schema_create', 'GRANT CREATE ON SCHEMA public TO '+ROLE, 'REVOKE CREATE ON SCHEMA public FROM '+ROLE),
                ('database_create', psycopg.sql.SQL('GRANT CREATE ON DATABASE {} TO '+ROLE).format(database), psycopg.sql.SQL('REVOKE CREATE ON DATABASE {} FROM '+ROLE).format(database)),
                ('database_temp', psycopg.sql.SQL('GRANT TEMP ON DATABASE {} TO '+ROLE).format(database), psycopg.sql.SQL('REVOKE TEMP ON DATABASE {} FROM '+ROLE).format(database)),
                ('connect_grant_option', psycopg.sql.SQL('GRANT CONNECT ON DATABASE {} TO '+ROLE+' WITH GRANT OPTION').format(database), psycopg.sql.SQL('REVOKE GRANT OPTION FOR CONNECT ON DATABASE {} FROM '+ROLE).format(database)),
                ('direct_execute', 'GRANT EXECUTE ON FUNCTION public.read_capacity_source_for_occupation(bytea,jsonb) TO '+ROLE, 'REVOKE EXECUTE ON FUNCTION public.read_capacity_source_for_occupation(bytea,jsonb) FROM '+ROLE),
                ('default_acl', 'ALTER DEFAULT PRIVILEGES FOR ROLE '+ROLE+' GRANT SELECT ON TABLES TO aos_runtime', 'ALTER DEFAULT PRIVILEGES FOR ROLE '+ROLE+' REVOKE SELECT ON TABLES FROM aos_runtime'),
                ('default_acl_grantee', 'ALTER DEFAULT PRIVILEGES FOR ROLE aos_app GRANT SELECT ON TABLES TO '+ROLE, 'ALTER DEFAULT PRIVILEGES FOR ROLE aos_app REVOKE SELECT ON TABLES FROM '+ROLE),
                ('inherit', 'ALTER ROLE '+ROLE+' INHERIT', 'ALTER ROLE '+ROLE+' NOINHERIT'),
                ('createdb', 'ALTER ROLE '+ROLE+' CREATEDB', 'ALTER ROLE '+ROLE+' NOCREATEDB'),
                ('membership_admin', 'GRANT aos_runtime TO '+ROLE+' WITH ADMIN OPTION', 'REVOKE ADMIN OPTION FOR aos_runtime FROM '+ROLE),
                ('membership_inherit', 'GRANT aos_runtime TO '+ROLE+' WITH INHERIT TRUE', 'GRANT aos_runtime TO '+ROLE+' WITH INHERIT FALSE'),
                *[(name, 'ALTER ROLE aos_runtime '+enable, 'ALTER ROLE aos_runtime '+disable)
                  for name,enable,disable in [
                      ('runtime_login','LOGIN','NOLOGIN'),('runtime_inherit','INHERIT','NOINHERIT'),
                      ('runtime_createdb','CREATEDB','NOCREATEDB'),('runtime_createrole','CREATEROLE','NOCREATEROLE'),
                      ('runtime_replication','REPLICATION','NOREPLICATION'),('runtime_bypassrls','BYPASSRLS','NOBYPASSRLS'),
                      ('runtime_super','SUPERUSER','NOSUPERUSER')]],
            ]
            for name, mutate, restore in faults:
                with isolated_owner() as admin:
                    admin.execute(mutate)
                try:
                    caller.execute("SET LOCAL TimeZone='UTC'")
                    apply_transaction_scope(caller, SCOPE)
                    fresh = command.model_copy(update={'bearer_token':sign(original[0]['maker'])})
                    with pytest.raises(ProviderCapacityConsumptionBlocked) as rejected:
                        consume_capacity_source_for_occupation(caller, fresh)
                    underlying = rejected.value.__context__
                    assert isinstance(underlying, psycopg.errors.InsufficientPrivilege), name
                    assert underlying.diag.message_primary == 'CAPACITY_OCCUPATION_CONTEXT_REQUIRED', name
                    print('occupation privilege denied', name)
                finally:
                    caller.rollback()
                    with isolated_owner() as admin:
                        admin.execute(restore)
                caller.execute("SET LOCAL TimeZone='UTC'")
                apply_transaction_scope(caller, SCOPE)
                restored = command.model_copy(update={'bearer_token':sign(original[0]['maker'])})
                assert consume_capacity_source_for_occupation(caller, restored) == source, name
                caller.rollback()
            _assert_occupation_epoch_concurrency(caller,source,command,sign,original[0]['maker'])
            _assert_occupation_independent_owner(caller,source,command,sign,original[0]['maker'],material)
    finally:
        with isolated_owner() as admin:
            admin.execute(psycopg.sql.SQL('REVOKE CONNECT ON DATABASE {} FROM '+ROLE).format(psycopg.sql.Identifier(admin.info.dbname)))
            admin.execute('DROP FUNCTION IF EXISTS public.read_capacity_source_for_occupation(bytea,jsonb)')
            admin.execute('DROP FUNCTION IF EXISTS public.require_capacity_occupation_source_installation()')
            from aos_api.aip_provider_capacity_occupation_epoch_profile import legacy_epoch_profile_restoration_statements
            for statement in legacy_epoch_profile_restoration_statements():
                admin.execute(statement)
            admin.execute('ALTER ROLE aos_provider_capacity_occupation NOLOGIN')
            admin.execute('REVOKE aos_runtime FROM aos_provider_capacity_occupation')

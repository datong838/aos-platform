"""Original epoch grants are dependencies, never Source publication proof."""
import pytest
from tests.aip.test_capacity_source_publication_transaction_pg import (
    native_signed_source,approved_command,private_database,signed_capacity_documents,
    source_proposal,source_inputs,drafted,original_inputs,SCOPE)


def test_publication_epoch_pair_reuses_original_guard(native_signed_source):
    from aos_api.aip_provider_capacity_publication_lock_boundary import require_publication_lock_boundary
    from aos_api.aip_provider_capacity_evidence_fence import _require_boundary
    from aos_api.aip_capacity_withdrawal_fence import require_withdrawal_fence
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer
    from aos_api.aip_provider_capacity_source_issuer import check_native_capacity_supplier_inputs
    f,actual_command,_,_,config=native_signed_source
    command,policy,attestation=actual_command()
    with connect_capacity_issuer(config,SCOPE) as conn:
        assert conn.pgconn.used_password is True
        require_publication_lock_boundary(conn)
        _require_boundary(conn)
        require_withdrawal_fence(conn)
        assert check_native_capacity_supplier_inputs(conn,command,policy,attestation,
            trust_roots=f['provider']).execution_allowed is False


@pytest.mark.parametrize('fault',['missing_evidence','missing_withdrawal','evidence_grant_option',
    'withdrawal_grant_option','public_evidence','public_withdrawal','extra_definer','public_definer',
    'evidence_body','withdrawal_mode','owner_login','owner_membership','owner_extra_select'])
def test_publication_lock_bridge_rejects_native_drift(native_signed_source,fault):
    from aos_api.aip_provider_capacity_publication_lock_boundary import (
        require_publication_lock_boundary,CapacityPublicationLockBlocked)
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    statements={
        'missing_evidence':'REVOKE EXECUTE ON FUNCTION public.aos_capacity_evidence_epoch_issuer_lock(text,text,text) FROM aos_capacity_publication_owner',
        'missing_withdrawal':'REVOKE EXECUTE ON FUNCTION public.aos_capacity_withdrawal_epoch_lock(text,text,text) FROM aos_capacity_publication_owner',
        'evidence_grant_option':'GRANT EXECUTE ON FUNCTION public.aos_capacity_evidence_epoch_issuer_lock(text,text,text) TO aos_capacity_publication_owner WITH GRANT OPTION',
        'withdrawal_grant_option':'GRANT EXECUTE ON FUNCTION public.aos_capacity_withdrawal_epoch_lock(text,text,text) TO aos_capacity_publication_owner WITH GRANT OPTION',
        'public_evidence':'GRANT EXECUTE ON FUNCTION public.aos_capacity_evidence_epoch_issuer_lock(text,text,text) TO PUBLIC',
        'public_withdrawal':'GRANT EXECUTE ON FUNCTION public.aos_capacity_withdrawal_epoch_lock(text,text,text) TO PUBLIC',
        'evidence_body':"CREATE OR REPLACE FUNCTION public.aos_capacity_evidence_epoch_issuer_lock(p_org text,p_project text,p_id text) RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$ BEGIN RETURN 0; END $$",
        'withdrawal_mode':'ALTER FUNCTION public.aos_capacity_withdrawal_epoch_lock(text,text,text) SECURITY INVOKER',
        'owner_login':'ALTER ROLE aos_capacity_publication_owner LOGIN',
        'owner_membership':'GRANT aos_runtime TO aos_capacity_publication_owner',
        'owner_extra_select':'GRANT SELECT ON public.twa_org TO aos_capacity_publication_owner',
    }
    with isolated_owner() as owner:
        require_publication_lock_boundary(owner)
        with pytest.raises(CapacityPublicationLockBlocked):
            with owner.transaction():
                if fault in {'extra_definer','public_definer'}:
                    owner.execute("CREATE FUNCTION public.publication_extra_definer_test() RETURNS bigint LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog AS 'SELECT 0::bigint'")
                    if fault=='extra_definer':
                        owner.execute('REVOKE EXECUTE ON FUNCTION public.publication_extra_definer_test() FROM PUBLIC')
                        owner.execute('GRANT EXECUTE ON FUNCTION public.publication_extra_definer_test() TO aos_capacity_publication_owner')
                else:
                    owner.execute(statements[fault])
                require_publication_lock_boundary(owner)
        require_publication_lock_boundary(owner)


def test_legacy_epoch_acl_stays_valid_without_new_pair(native_signed_source):
    from aos_api.aip_provider_capacity_publication_lock_boundary import (
        require_publication_lock_boundary,audited_publication_epoch_caller,CapacityPublicationLockBlocked)
    from aos_api.aip_provider_capacity_evidence_fence import _require_boundary
    from aos_api.aip_capacity_withdrawal_fence import require_withdrawal_fence
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    with isolated_owner() as owner:
        require_publication_lock_boundary(owner)
        with pytest.raises(CapacityPublicationLockBlocked):
            with owner.transaction():
                for signature in ['public.aos_capacity_evidence_epoch_issuer_lock(text,text,text)',
                    'public.aos_capacity_withdrawal_epoch_lock(text,text,text)']:
                    owner.execute('REVOKE EXECUTE ON FUNCTION '+signature+' FROM aos_capacity_publication_owner')
                assert audited_publication_epoch_caller(owner) is None
                _require_boundary(owner)
                require_withdrawal_fence(owner)
                require_publication_lock_boundary(owner)
        require_publication_lock_boundary(owner)


@pytest.mark.parametrize('table',['aip_capacity_evidence_epoch','aip_capacity_withdrawal_epoch'])
def test_publication_owner_cannot_access_neutral_epoch_tables(native_signed_source,table):
    import psycopg
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    with isolated_owner() as owner:
        owner.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with owner.transaction():
                owner.execute('SELECT * FROM public.'+table)


@pytest.fixture
def nested_epoch_reader(native_signed_source):
    """Temporary primitive harness; the original issuer denies it as Source."""
    from uuid import uuid4
    from psycopg import sql
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    from aos_api.aip_provider_capacity_issuer_connection import connect_capacity_issuer
    from aos_api.aip_provider_capacity_source_issuer import check_native_capacity_supplier_inputs
    f,actual_command,basis,source,config=native_signed_source
    command,policy,attestation=actual_command()
    with connect_capacity_issuer(config,SCOPE) as verified:
        assert check_native_capacity_supplier_inputs(verified,command,policy,attestation,
            trust_roots=f['provider']).execution_allowed is False
    with isolated_owner() as owner:
        allocation=owner.execute('SELECT proposal_id FROM public.aip_action_approval_event '
            'WHERE org_id=%s AND project_id=%s AND approval_event_id=%s',
            (*SCOPE.key,source.allocation_approval_ref.asset_id)).fetchone()['proposal_id']
    args=(basis.evidence_ref.asset_id,command.approved_proposal.asset_id,allocation)
    name='publication_epoch_harness_'+uuid4().hex
    ident=sql.Identifier('public',name)
    with connect_capacity_issuer(config,SCOPE) as caller:
        assert caller.pgconn.used_password is True
        with isolated_owner() as owner:
            owner.execute(sql.SQL("""CREATE FUNCTION {}(e text,s text,a text) RETURNS jsonb
                LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog AS $body$
                SELECT jsonb_build_object('owner',current_user,'session',session_user,
                    'xid',pg_current_xact_id()::text,'pid',pg_backend_pid(),
                    'evidence',public.aos_capacity_evidence_epoch_issuer_lock('org-org','dev-project',e),
                    'source',public.aos_capacity_withdrawal_epoch_lock('org-org','dev-project',s),
                    'allocation',public.aos_capacity_withdrawal_epoch_lock('org-org','dev-project',a))
                $body$""").format(ident))
            owner.execute(sql.SQL('ALTER FUNCTION {}(text,text,text) OWNER TO aos_capacity_publication_owner').format(ident))
            owner.execute(sql.SQL('REVOKE EXECUTE ON FUNCTION {}(text,text,text) FROM PUBLIC').format(ident))
            owner.execute(sql.SQL('GRANT EXECUTE ON FUNCTION {}(text,text,text) TO aos_provider_capacity_issuer').format(ident))
        # The primitive harness was installed after the connection audit's
        # SERIALIZABLE snapshot. Start a fresh transaction on the same SCRAM
        # session; the harness still cannot pass the formal Source guard.
        caller.rollback()
        caller.execute('SET LOCAL search_path=pg_catalog,public,pg_temp')
        caller.execute("SET LOCAL TimeZone='UTC'")
        caller.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        try:
            yield caller,ident,args,config
        finally:
            caller.rollback()
            with isolated_owner() as owner:
                owner.execute(sql.SQL('DROP FUNCTION {}(text,text,text)').format(ident))
    with connect_capacity_issuer(config,SCOPE) as rechecked:
        assert check_native_capacity_supplier_inputs(rechecked,command,policy,attestation,
            trust_roots=f['provider']).execution_allowed is False


def test_real_private_session_nested_owner_keeps_epochs_until_caller_commit(nested_epoch_reader):
    from threading import Event,Thread
    import time
    from psycopg import sql
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    caller,ident,args,_=nested_epoch_reader
    before=caller.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
    result=caller.execute(sql.SQL('SELECT {}(%s::text,%s::text,%s::text) AS result').format(ident),args).fetchone()['result']
    assert result==dict(owner='aos_capacity_publication_owner',session='aos_provider_capacity_issuer',
        xid=before['xid'],pid=before['pid'],evidence=0,source=0,allocation=0)
    targets=[('aip_capacity_evidence_epoch','bundle_id',args[0]),
        ('aip_capacity_withdrawal_epoch','proposal_id',args[1]),
        ('aip_capacity_withdrawal_epoch','proposal_id',args[2])]
    started=[Event() for _ in targets];done=[Event() for _ in targets]
    writer_pids={};errors={};threads=[]
    def writer(index,target):
        try:
            with isolated_owner() as owner:
                owner.execute("SET LOCAL statement_timeout='5s'")
                writer_pids[index]=owner.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
                started[index].set()
                owner.execute(sql.SQL('UPDATE public.{} SET epoch=epoch WHERE org_id=%s AND project_id=%s AND {}=%s')
                    .format(sql.Identifier(target[0]),sql.Identifier(target[1])),(*SCOPE.key,target[2]))
        except BaseException as error:
            errors[index]=error
        finally:
            done[index].set()
    try:
        for index,target in enumerate(targets):
            thread=Thread(target=writer,args=(index,target));threads.append(thread);thread.start()
        assert all(event.wait(2) for event in started),errors
        deadline=time.monotonic()+2
        blocked=set()
        with isolated_owner() as observer:
            while time.monotonic()<deadline:
                blocked={i for i,pid in writer_pids.items() if before['pid'] in observer.execute(
                    'SELECT pg_blocking_pids(%s) AS pids',(pid,)).fetchone()['pids']}
                if len(blocked)==3:break
                time.sleep(0.02)
        assert blocked=={0,1,2} and not any(e.is_set() for e in done),errors
        caller.commit()
        assert all(event.wait(3) for event in done),errors
        assert not errors,errors
        with isolated_owner() as owner:
            for table,column,asset_id in targets:
                assert owner.execute(sql.SQL('SELECT epoch FROM public.{} WHERE org_id=%s AND project_id=%s AND {}=%s')
                    .format(sql.Identifier(table),sql.Identifier(column)),(*SCOPE.key,asset_id)).fetchone()['epoch']==0
        print('CAPACITY_NESTED_EPOCH_COMMIT_PROOF actual_scram=true same_native_xid_pid=true original_private_session=true nested_owner=true three_actual_blocked_writers=true caller_commit_released=true epochs_unchanged=true source_issued=false')
    finally:
        caller.rollback()
        for thread in threads:thread.join(timeout=6)


@pytest.mark.parametrize('fault',['wrong_session','canary','blank_withdrawal','missing_withdrawal','nonzero_withdrawal'])
def test_nested_original_locks_reject_wrong_context(nested_epoch_reader,fault):
    import psycopg
    from psycopg import sql
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    caller,ident,args,_=nested_epoch_reader
    values=list(args)
    if fault=='wrong_session':
        with isolated_owner() as owner:
            owner.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with owner.transaction():
                    owner.execute(sql.SQL('SELECT {}(%s::text,%s::text,%s::text)').format(ident),values)
        return
    if fault=='blank_withdrawal':values[1]=''
    if fault=='missing_withdrawal':values[1]='missing-original-withdrawal-epoch'
    if fault=='nonzero_withdrawal':
        # Only this fixture's isolated mutable epoch changes. A fresh native
        # snapshot must reject it; retain the actual PostgreSQL exception.
        caller.rollback()
        try:
            with isolated_owner() as owner:
                owner.execute('UPDATE public.aip_capacity_withdrawal_epoch SET epoch=1 '
                    'WHERE org_id=%s AND project_id=%s AND proposal_id=%s',(*SCOPE.key,args[1]))
            caller.execute('SET LOCAL search_path=pg_catalog,public,pg_temp')
            caller.execute("SET LOCAL TimeZone='UTC'")
            caller.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with caller.transaction():
                    caller.execute(sql.SQL('SELECT {}(%s::text,%s::text,%s::text)').format(ident),values)
        finally:
            caller.rollback()
            with isolated_owner() as owner:
                owner.execute('UPDATE public.aip_capacity_withdrawal_epoch SET epoch=0 '
                    'WHERE org_id=%s AND project_id=%s AND proposal_id=%s',(*SCOPE.key,args[1]))
        return
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with caller.transaction():
            if fault=='canary':caller.execute("SELECT set_config('aos.org_id','dev-org',true)")
            caller.execute(sql.SQL('SELECT {}(%s::text,%s::text,%s::text)').format(ident),values)


def test_temporary_nested_harness_does_not_authorize_a_source(nested_epoch_reader):
    from aos_api.aip_provider_capacity_issuer_connection import (
        connect_capacity_issuer,ProviderCapacityIssuerConnectionBlocked)
    _,_,_,config=nested_epoch_reader
    # A fresh native transaction sees the test-only extra definer grant.
    # The harness is therefore not a formal publication entrypoint.
    with pytest.raises(ProviderCapacityIssuerConnectionBlocked,match='CAPACITY_ISSUER_EFFECTIVE_DEFINER_PERMISSION_DRIFTED'):
        with connect_capacity_issuer(config,SCOPE):
            pytest.fail('temporary lock harness cannot enter original formal Source guard')

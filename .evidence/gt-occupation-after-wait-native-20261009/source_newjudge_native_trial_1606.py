"""Owned integration: original signed Source and original new-Judge parent, no execution."""
from contextlib import contextmanager
from pathlib import Path
import json
import os
from uuid import UUID,uuid4
import psycopg
import pytest
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from aos_api.tenant_scope import TenantScope,apply_transaction_scope
from tests.aip._runtime_guard_history_fixture import isolated_owner

def run_source_newjudge_trial(params,command,exact,source,provider,caller,issuer_factory,
        https_signer,guard_issuer_factory,guard_consumer_factory,tmp_path,base):
    from aos_api.aip_physical_capacity_occupation_authority import (
        occupation_judge_fact_statements,occupation_judge_parent_debit_statements)
    from after_wait_judge_trial import test_exact_signed_rule_new_original_suite
    from aos_api.aip_provider_capacity_source_consumer import _consumption_packet
    raw=_consumption_packet(command)
    source_ref=exact.model_dump(mode='json',by_alias=True)
    @contextmanager
    def native_factory(scope):
        with psycopg.connect(**params,row_factory=dict_row) as conn:
            conn.isolation_level=psycopg.IsolationLevel.SERIALIZABLE
            conn.execute("SET LOCAL TimeZone='UTC'")
            apply_transaction_scope(conn,scope)
            identity=conn.execute('SELECT session_user AS login,current_user AS role').fetchone()
            assert conn.pgconn.used_password and identity==dict(login='aos_provider_capacity_occupation',role='aos_runtime')
            yield conn
    def prefix(conn):
        # Original Judge request/parent schema exists only after its own Store setup.
        with isolated_owner() as admin:
            for statement in (*occupation_judge_fact_statements(),*occupation_judge_parent_debit_statements()):
                admin.execute(statement)
            from aos_api.aip_physical_capacity_occupation_authority import occupation_plan_risk_statements
            for statement in occupation_plan_risk_statements():admin.execute(statement)
            from aos_api.aip_physical_capacity_occupation_authority import occupation_prepared_call_statements
            for statement in occupation_prepared_call_statements():admin.execute(statement)
            from aos_api.aip_physical_capacity_occupation_authority import occupation_target_call_statements
            for statement in occupation_target_call_statements():admin.execute(statement)
            from aos_api.aip_physical_capacity_occupation_authority import occupation_target_ledger_statements,SCHEMA,OWNER
            for statement in occupation_target_ledger_statements():admin.execute(statement)
            for tag in ('occupation','occupation_event'):
                name='public.test_ledger_'+tag+'_constraint_probe'
                admin.execute(f"CREATE FUNCTION {name}(p_id uuid) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $probe$ BEGIN SET CONSTRAINTS {SCHEMA}.require_{tag}_finalization IMMEDIATE; END $probe$")
                admin.execute(f'ALTER FUNCTION {name}(uuid) OWNER TO '+OWNER)
                admin.execute(f'REVOKE ALL ON FUNCTION {name}(uuid) FROM PUBLIC')
                admin.execute(f'GRANT EXECUTE ON FUNCTION {name}(uuid) TO aos_runtime')
            name='public.test_ledger_exact_readback'
            admin.execute(f"""CREATE FUNCTION {name}(p_id uuid) RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog AS $probe$
                SELECT jsonb_build_object('root',(SELECT to_jsonb(r) FROM {SCHEMA}.call_occupation r WHERE call_id=p_id),
                  'event',(SELECT to_jsonb(e) FROM {SCHEMA}.call_occupation_event e WHERE call_id=p_id AND event_seq=1),
                  'actual_inflight_requests',(SELECT count(*) FROM {SCHEMA}.call_occupation WHERE counts_as_inflight),
                  'physical_prepared_requests',(SELECT count(*) FROM {SCHEMA}.prepared_parent_debit),
                  'physical_prepared_tokens',(SELECT coalesce(sum(token_units),0) FROM {SCHEMA}.prepared_parent_debit))
              $probe$""")
            admin.execute(f'ALTER FUNCTION {name}(uuid) OWNER TO '+OWNER)
            admin.execute(f'REVOKE ALL ON FUNCTION {name}(uuid) FROM PUBLIC')
            admin.execute(f'GRANT EXECUTE ON FUNCTION {name}(uuid) TO aos_runtime')
            catalog=[]
            for table_name in ('call_occupation','call_occupation_event'):
                relation=SCHEMA+'.'+table_name
                row=admin.execute("SELECT relrowsecurity,relforcerowsecurity,pg_get_userbyid(relowner) AS owner,has_table_privilege('aos_runtime',oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE') AS runtime_privilege FROM pg_class WHERE oid=%s::regclass",(relation,)).fetchone()
                assert row==dict(relrowsecurity=True,relforcerowsecurity=True,owner=OWNER,runtime_privilege=False)
                triggers=admin.execute("SELECT tgname,tgdeferrable,tginitdeferred FROM pg_trigger WHERE tgrelid=%s::regclass AND NOT tgisinternal ORDER BY tgname",(relation,)).fetchall()
                assert len(triggers)==3 and any(t['tgdeferrable'] and t['tginitdeferred'] for t in triggers)
                checks=admin.execute("SELECT conname,pg_get_expr(conbin,conrelid) AS expr FROM pg_constraint WHERE conrelid=%s::regclass AND contype='c' ORDER BY conname",(relation,)).fetchall()
                catalog.append(dict(table=table_name,acl=row,triggers=triggers,checks=checks))
            Path(__file__).resolve().parent.joinpath('ledger-catalog.json').write_text(json.dumps(catalog,indent=2)+'\n')
            table='aos_physical_capacity_occupation_private.prepared_call_occupation'
            input_constraint=admin.execute("SELECT pg_get_expr(conbin,conrelid) AS expr FROM pg_constraint WHERE conrelid=%s::regclass AND conname='prepared_call_occupation_input_hash_check'",(table,)).fetchone()['expr']
            row=admin.execute("SELECT relrowsecurity,relforcerowsecurity,pg_get_userbyid(relowner) AS owner,has_table_privilege('aos_runtime',oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE') AS runtime_privilege FROM pg_class WHERE oid=%s::regclass",(table,)).fetchone()
            assert row==dict(relrowsecurity=True,relforcerowsecurity=True,owner='aos_physical_capacity_occupation_owner',runtime_privilege=False)
            triggers=admin.execute("SELECT tgname,tgdeferrable,tginitdeferred FROM pg_trigger WHERE tgrelid=%s::regclass AND NOT tgisinternal ORDER BY tgname",(table,)).fetchall()
            assert len(triggers)==3 and any(t['tgdeferrable'] and t['tginitdeferred'] for t in triggers)
            Path(__file__).resolve().parent.joinpath('catalog.json').write_text(json.dumps(dict(table=table,acl=row,triggers=triggers,input_constraint=input_constraint,execution_allowed=False),indent=2)+'\n')
        conn.execute('SELECT public.prepare_capacity_occupation_account_guard(%s,%s)',(raw,Jsonb(source_ref))).fetchone()
    def probe(conn,body,target,judge):
        args=(raw,Jsonb(source_ref),UUID(target.parent_limit.parent_hold_ref.resource_id),target.request_id,target.request_hash,UUID(judge.parent_limit.parent_hold_ref.resource_id),judge.request_id,judge.request_hash)
        key=uuid4()
        def prepare(identity=key,actual=args):
            return conn.execute('SELECT public.prepare_capacity_plan_risk(%s,%s,%s,%s,%s,%s,%s,%s,%s) AS plan',(*actual,identity)).fetchone()['plan']
        plan=prepare();assert plan==prepare()
        for sql in ("SELECT * FROM aos_physical_capacity_occupation_private.prepared_call_occupation", "INSERT INTO aos_physical_capacity_occupation_private.prepared_call_occupation DEFAULT VALUES", "UPDATE aos_physical_capacity_occupation_private.prepared_call_occupation SET state='admitted'", "DELETE FROM aos_physical_capacity_occupation_private.prepared_call_occupation", "TRUNCATE aos_physical_capacity_occupation_private.prepared_call_occupation"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with conn.transaction():conn.execute(sql)
        legs=plan['immutable']['legs'];assert len(legs)==4
        original_hash=legs[0]['case']['inputArtifact']['contentHash']
        expression=json.loads(Path(__file__).resolve().parent.joinpath('catalog.json').read_text())['input_constraint']
        def accepts(value):return conn.execute('SELECT ('+expression+') AS allowed FROM (SELECT %s::text AS input_hash) original',(value,)).fetchone()['allowed']
        accepted=accepts(original_hash)
        Path(__file__).resolve().parent.joinpath('hash-check.json').write_text(json.dumps(dict(original_input_hash=original_hash,installed_constraint=expression,accepted=accepted),indent=2)+'\n')
        assert accepted, 'Original verified raw input hash rejected by actual installed call CHECK'
        assert not accepts('sha256:'+original_hash)
        assert not accepts(original_hash[:-1])
        assert not accepts(original_hash.upper())
        assert {(l['case']['caseId'],l['purpose']) for l in legs}=={(c['caseId'],p) for c in judge.request['cases'] for p in ('target','judge')}
        assert [p['upperBoundMinor'] for p in plan['immutable']['parentRisks']]==[10,10]
        assert plan['executionAllowed'] is False
        assert plan['physicalPreparedRequests']==plan['physicalPreparedTokens']==0
        from aos_api.aip_eval_pack_registry import AipEvalPackRegistry
        from aos_api.ecommerce_content_pre_review_pack import build_content_pre_review_eval_packs
        from aos_api.ecommerce_content_pre_review_eval import GRAPH_ID,build_content_pre_review_graph
        from aos_api.aip_eval_contracts import AssetRevisionRef,AssetType
        from aos_api.aip_logic_graph_models import compute_logic_graph_hash
        sr=plan['immutable']['originalFacts']['target']['application']['suiteRef']
        suite_row=conn.execute('SELECT * FROM public.aip_eval_suite_revision WHERE org_id=%s AND project_id=%s AND suite_id=%s AND revision=%s',('org-org','dev-project',sr['assetId'],int(sr['revision']))).fetchone()
        suite=AipEvalPackRegistry._suite_from_row(suite_row)
        suite_raw=json.dumps(suite.model_dump(mode='json',by_alias=True,exclude={'content_hash'}),ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
        original_target=AssetRevisionRef(assetType=AssetType.LOGIC_GRAPH,assetId=GRAPH_ID,revision='1',contentHash=compute_logic_graph_hash(build_content_pre_review_graph()))
        _,pack=build_content_pre_review_eval_packs(original_target)
        case=suite.cases[0];ref=case.input_artifact
        input_raw=json.dumps(pack.artifacts[(ref.artifact_id,ref.revision)],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
        debit_id=uuid4();intent_id=uuid4()
        intent_args=(raw,Jsonb(source_ref),args[2],target.request_id,target.request_hash,debit_id,1,suite_raw,case.case_id,input_raw,intent_id)
        def original_intent(actual=intent_args):return conn.execute('SELECT public.prepare_capacity_execution_intent(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) AS fact',actual).fetchone()['fact']
        intent=original_intent();assert original_intent()==intent
        ib=intent['immutable'];pb=plan['immutable']
        assert ib['callerXid']==pb['callerXid'] and ib['callerPid']==pb['callerPid'] and ib['callerLogin']==pb['callerLogin']
        assert ib['inputHash']==ref.content_hash==original_hash
        assert ib['requestId']==target.request_id and ib['application']==pb['originalFacts']['target']['application']
        for bad in (input_raw+b' ',None):
            with conn.transaction(force_rollback=True):
                with pytest.raises(psycopg.errors.CheckViolation,match='INPUT_BYTES'):original_intent((*intent_args[:9],bad,intent_id))
        call_id=uuid4()
        call_args=(raw,Jsonb(source_ref),key,intent_id,call_id)
        def call(actual=call_args):return conn.execute('SELECT public.prepare_capacity_target_call(%s,%s::jsonb,%s::uuid,%s::uuid,%s::uuid) AS fact',actual).fetchone()['fact']
        prepared=call();assert call()==prepared
        assert prepared['immutable']['state']=='prepared_only' and prepared['executionAllowed'] is False
        assert prepared['immutable']['inputHash']==ref.content_hash and prepared['immutable']['intentHash']==intent['contentHash']
        assert prepared['immutable']['planHash']==plan['contentHash']
        negatives=[]  # Frozen producer negative matrix1613; no duplicate deadline work.
        ledger_args=(raw,Jsonb(source_ref),key,intent_id,call_id)
        def initialize(actual=ledger_args):return conn.execute('SELECT public.prepare_capacity_target_occupation(%s,%s::jsonb,%s::uuid,%s::uuid,%s::uuid) AS fact',actual).fetchone()['fact']
        before=conn.execute('SELECT public.test_ledger_exact_readback(%s::uuid) AS fact',(call_id,)).fetchone()['fact']
        from aos_api.aip_physical_capacity_occupation import prepare_target_occupation
        from aos_api.aip_model_eval_execution_owner import ModelEvalOwnerRejected
        import threading,time
        from datetime import datetime,timezone
        with conn.transaction(force_rollback=True):
            ledger=initialize();assert initialize()==ledger
            typed=prepare_target_occupation(conn,TenantScope('org-org','dev-project'),command,key,intent_id,call_id)
            assert typed.model_dump(mode='json',by_alias=True)==ledger
            stored=conn.execute('SELECT public.test_ledger_exact_readback(%s::uuid) AS fact',(call_id,)).fetchone()['fact']
            assert stored['root']['immutable']==ledger['immutable'] and stored['event']['immutable']==ledger['initialEvent']
            assert stored['actual_inflight_requests']==0
        after_positive=conn.execute('SELECT public.test_ledger_exact_readback(%s::uuid) AS fact',(call_id,)).fetchone()['fact']
        assert after_positive['root'] is None and after_positive['event'] is None
        deadline=datetime.fromisoformat(plan['immutable']['originalFacts']['judge']['approvalSnapshot']['expires_at'])
        xid=plan['immutable']['callerXid'];pid=plan['immutable']['callerPid']
        now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now'];assert now<deadline,'Approval expired before actual wait; not afterwait proof'
        ready=threading.Event();done=threading.Event();errors=[];proof=dict(caller_xid=xid,caller_pid=pid,deadline=deadline.isoformat(),before_wait=now.isoformat(),positive_root_rollback=True,test_only_relation_lock=True,execution_allowed=False)
        def holder_worker():
            try:
                with isolated_owner() as holder:
                    holder.execute('SET LOCAL statement_timeout=5000')
                    holder.execute('LOCK TABLE aos_physical_capacity_occupation_private.call_occupation IN EXCLUSIVE MODE')
                    hp=holder.execute('SELECT pg_backend_pid() AS pid,clock_timestamp() AS now').fetchone();proof['holder_pid']=hp['pid'];ready.set()
                    started=time.monotonic();seen=False;observations=0
                    while time.monotonic()-started<80:
                        holder.execute('SELECT pg_stat_clear_snapshot()')
                        row=holder.execute("SELECT clock_timestamp() AS now,pg_blocking_pids(%s) AS blockers,(SELECT wait_event_type FROM pg_stat_activity WHERE pid=%s) AS wait_type,(SELECT wait_event FROM pg_stat_activity WHERE pid=%s) AS wait_event,EXISTS(SELECT 1 FROM pg_locks WHERE pid=%s AND relation='aos_physical_capacity_occupation_private.call_occupation'::regclass AND mode='RowExclusiveLock' AND NOT granted) AS insert_wait",(pid,pid,pid,pid)).fetchone()
                        if hp['pid'] in row['blockers'] and row['wait_type']=='Lock' and row['insert_wait']:
                            if not seen:
                                assert row['now']<deadline,'No observed blocking before deadline';proof['first_blocked_at']=row['now'].isoformat();seen=True
                            observations+=1
                            if row['now']>deadline:
                                proof.update(release_after_deadline=row['now'].isoformat(),blockers=row['blockers'],wait_event=row['wait_event'],insert_lock_mode='RowExclusiveLock',blocking_observations=observations);break
                        time.sleep(.1)
                    else:raise AssertionError('Actual insert blocker not observed through original expiry')
                    assert seen and observations>1
                    holder.rollback();proof['holder_released']=True
            except BaseException as e:errors.append(type(e).__name__+': '+str(e))
            finally:ready.set();done.set()
        worker=threading.Thread(target=holder_worker,name='isolated-relation-blocker');worker.start();assert ready.wait(6) and not errors
        actual=None
        try:
            with conn.transaction(force_rollback=True):initialize()
        except psycopg.Error as err:
            actual=dict(sqlstate=err.sqlstate,message=err.diag.message_primary)
        finally:worker.join(85)
        proof.update(actual=actual,holder_errors=errors,holder_done=done.is_set())
        Path(__file__).resolve().parent.joinpath('after-wait-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
        assert done.is_set() and not errors
        assert actual==dict(sqlstate='23514',message='CAPACITY_JUDGE_CURRENT_DEADLINES_REQUIRED')
        after=conn.execute('SELECT public.test_ledger_exact_readback(%s::uuid) AS fact',(call_id,)).fetchone()['fact']
        assert after['root'] is None and after['event'] is None and after['actual_inflight_requests']==0
        with conn.transaction(force_rollback=True):
            with pytest.raises(ModelEvalOwnerRejected,match='^CAPACITY_TYPED_OCCUPATION_PREPARATION_REQUIRED$'):
                prepare_target_occupation(conn,TenantScope('org-org','dev-project'),command,key,intent_id,call_id)
        identity=conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone();assert identity==dict(xid=xid,pid=pid)
        proof.update(after_root=after['root'],after_event=after['event'],samecaller_restored=True,wrapper_fixed_denial=True)
        Path(__file__).resolve().parent.joinpath('after-wait-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
        Path(__file__).resolve().parent.joinpath('wrapper-green.json').write_text(json.dumps(dict(plan=plan,typed=typed.model_dump(mode='json',by_alias=True),positive_savepoint_rollback=True,after_wait_fixed_denial=True,execution_allowed=False),indent=2)+'\n')
        Path(__file__).resolve().parent.joinpath('ledger-green.json').write_text(json.dumps(dict(plan=plan,intent=intent,call=prepared,ledger=ledger,before=before,stored=stored,positive_savepoint_rollback=True,after_wait=proof,execution_allowed=False),indent=2)+'\n')
        # Frozen complete-plan negative matrix1610; do not repeat old authority work.
        (Path(__file__).resolve().parent/'complete-plan-risk.json').write_text(json.dumps(dict(plan=plan,faults_previously_frozen=True,actual_inflight_added=0,per_leg_price_assigned=False),indent=2)+'\n')
        return dict(plan=plan,execution_allowed=False)
    def finish(conn):
        xid=conn.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid']
        with pytest.raises(psycopg.errors.CheckViolation,match='CAPACITY_PARENT_FINALIZE_REQUIRED'):
            conn.commit()
        assert conn.info.transaction_status==psycopg.pq.TransactionStatus.IDLE
        return dict(xid=xid,actual_commit_rejected=True,sqlstate='23514',execution_allowed=False)
    trial_path=tmp_path/'source-newjudge';trial_path.mkdir()
    try:
        test_exact_signed_rule_new_original_suite(caller,issuer_factory,https_signer,
            guard_issuer_factory,guard_consumer_factory,trial_path,source_provider=provider,
            whole_caller_factory=native_factory,source_prefix=prefix,source_probe=probe,
            source_finish=finish if os.environ.get('AOS_NEW_JUDGE_INTENT_NATIVE') == '1' else None,
            source_native_only=os.environ.get('AOS_NEW_JUDGE_INTENT_NATIVE') == '1')
    finally:
        with isolated_owner() as admin:
            from aos_api.aip_physical_capacity_occupation_authority import PLAN_RISK,PLAN_FACT
            for tag in ('occupation','occupation_event'):
                admin.execute('DROP FUNCTION IF EXISTS public.test_ledger_'+tag+'_constraint_probe(uuid)')
            admin.execute('DROP FUNCTION IF EXISTS public.test_ledger_exact_readback(uuid)')
            from aos_api.aip_physical_capacity_occupation_authority import TARGET_OCCUPATION
            admin.execute('DROP FUNCTION IF EXISTS '+TARGET_OCCUPATION)
            from aos_api.aip_physical_capacity_occupation_authority import TARGET_CALL
            admin.execute('DROP FUNCTION IF EXISTS '+TARGET_CALL)
            admin.execute('DROP FUNCTION IF EXISTS '+PLAN_RISK)
            admin.execute('DROP FUNCTION IF EXISTS '+PLAN_FACT)

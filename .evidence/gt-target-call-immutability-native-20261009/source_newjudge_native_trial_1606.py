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
    from tests.aip.test_model_eval_judge_authority_pg import test_exact_signed_rule_new_original_suite
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
            from aos_api.aip_physical_capacity_occupation_authority import OWNER,SCHEMA
            for operation in ('update','delete','truncate','joint_constraint'):
                statement={
                    'update':f"UPDATE {SCHEMA}.prepared_call_occupation SET state='prepared_only' WHERE call_id=p_id",
                    'delete':f"DELETE FROM {SCHEMA}.prepared_call_occupation WHERE call_id=p_id",
                    'truncate':f"TRUNCATE {SCHEMA}.prepared_call_occupation",
                    'joint_constraint':f"SET CONSTRAINTS {SCHEMA}.require_joint_finalization IMMEDIATE",
                }[operation]
                name='public.test_target_call_'+operation+'_probe'
                admin.execute(f"CREATE FUNCTION {name}(p_id uuid) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $probe$ BEGIN {statement}; END $probe$")
                admin.execute(f'ALTER FUNCTION {name}(uuid) OWNER TO '+OWNER)
                admin.execute(f'REVOKE ALL ON FUNCTION {name}(uuid) FROM PUBLIC')
                admin.execute(f'GRANT EXECUTE ON FUNCTION {name}(uuid) TO aos_runtime')
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
        with conn.transaction(force_rollback=True):
            with pytest.raises(psycopg.errors.InsufficientPrivilege,match='CAPACITY_INTENT_IMMUTABLE') as empty_truncate:
                conn.execute('SELECT public.test_target_call_truncate_probe(%s::uuid)',(uuid4(),))
        Path(__file__).resolve().parent.joinpath('empty-call-truncate.json').write_text(json.dumps(dict(sqlstate=empty_truncate.value.sqlstate,custom_before_truncate_trigger_tested=True,existing_rows=0),indent=2)+'\n')
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
        negatives=[]  # Six producer negatives already frozen in native1613; this wave tests new concerns.
        immutable_checks=[]
        for operation in ('update','delete','truncate','joint_constraint'):
            expected={'joint_constraint':psycopg.errors.CheckViolation,'truncate':psycopg.errors.ObjectInUse}.get(operation,psycopg.errors.InsufficientPrivilege)
            message={'joint_constraint':'CAPACITY_PARENT_FINALIZE_REQUIRED','truncate':'pending trigger events'}.get(operation,'CAPACITY_INTENT_IMMUTABLE')
            with conn.transaction(force_rollback=True):
                with pytest.raises(expected,match=message) as denied:
                    conn.execute('SELECT public.test_target_call_'+operation+'_probe(%s::uuid)',(call_id,))
            assert call()==prepared
            immutable_checks.append(dict(operation=operation,sqlstate=denied.value.sqlstate,message=message,existing_row_unchanged=True))
        Path(__file__).resolve().parent.joinpath('existing-call-immutability.json').write_text(json.dumps(dict(checks=immutable_checks,call_hash=prepared['contentHash'],direct_target_call_constraint_tested=True,execution_allowed=False),indent=2)+'\n')
        Path(__file__).resolve().parent.joinpath('trusted-target-call-green.json').write_text(json.dumps(dict(plan=plan,intent=intent,call=prepared,same_transaction=True,original_input_bytes_verified=True,negatives=negatives,execution_allowed=False,arbitrary_one_minor_is_preparation_only=True),indent=2)+'\n')
        faults=[]
        for fault,identity,actual in [('new-plan',uuid4(),args),('null-plan',None,args),('wrong-target',key,(*args[:2],uuid4(),*args[3:])),('wrong-hash',key,(*args[:4],'0'*64,*args[5:]))]:
            with conn.transaction(force_rollback=True):
                with pytest.raises(psycopg.errors.CheckViolation):prepare(identity,actual)
            faults.append(fault)
        with conn.transaction(force_rollback=True):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):conn.execute('SELECT * FROM aos_physical_capacity_occupation_private.prepared_plan_risk')
        with conn.transaction(force_rollback=True):
            with pytest.raises(psycopg.errors.CheckViolation,match='CAPACITY_PARENT_FINALIZE_REQUIRED'):conn.execute('SET CONSTRAINTS ALL IMMEDIATE')
        (Path(__file__).resolve().parent/'complete-plan-risk.json').write_text(json.dumps(dict(plan=plan,faults=faults,actual_inflight_added=0,per_leg_price_assigned=False),indent=2)+'\n')
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
            for operation in ('update','delete','truncate','joint_constraint'):
                admin.execute('DROP FUNCTION IF EXISTS public.test_target_call_'+operation+'_probe(uuid)')
            from aos_api.aip_physical_capacity_occupation_authority import TARGET_CALL
            admin.execute('DROP FUNCTION IF EXISTS '+TARGET_CALL)
            admin.execute('DROP FUNCTION IF EXISTS '+PLAN_RISK)
            admin.execute('DROP FUNCTION IF EXISTS '+PLAN_FACT)

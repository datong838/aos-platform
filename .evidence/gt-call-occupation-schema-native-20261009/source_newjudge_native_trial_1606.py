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
            table='aos_physical_capacity_occupation_private.prepared_call_occupation'
            row=admin.execute("SELECT relrowsecurity,relforcerowsecurity,pg_get_userbyid(relowner) AS owner,has_table_privilege('aos_runtime',oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE') AS runtime_privilege FROM pg_class WHERE oid=%s::regclass",(table,)).fetchone()
            assert row==dict(relrowsecurity=True,relforcerowsecurity=True,owner='aos_physical_capacity_occupation_owner',runtime_privilege=False)
            triggers=admin.execute("SELECT tgname,tgdeferrable,tginitdeferred FROM pg_trigger WHERE tgrelid=%s::regclass AND NOT tgisinternal ORDER BY tgname",(table,)).fetchall()
            assert len(triggers)==3 and any(t['tgdeferrable'] and t['tginitdeferred'] for t in triggers)
            Path(__file__).resolve().parent.joinpath('catalog.json').write_text(json.dumps(dict(table=table,acl=row,triggers=triggers,execution_allowed=False),indent=2)+'\n')
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
        assert {(l['case']['caseId'],l['purpose']) for l in legs}=={(c['caseId'],p) for c in judge.request['cases'] for p in ('target','judge')}
        assert [p['upperBoundMinor'] for p in plan['immutable']['parentRisks']]==[10,10]
        assert plan['executionAllowed'] is False
        assert plan['physicalPreparedRequests']==plan['physicalPreparedTokens']==0
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
            admin.execute('DROP FUNCTION IF EXISTS '+PLAN_RISK)
            admin.execute('DROP FUNCTION IF EXISTS '+PLAN_FACT)

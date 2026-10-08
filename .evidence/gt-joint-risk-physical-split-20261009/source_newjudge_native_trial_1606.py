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
            if os.environ.get('AOS_NEW_JUDGE_INTENT_NATIVE') == '1':
                from aos_api.aip_physical_capacity_occupation_authority import occupation_judge_intent_statements
                for statement in occupation_judge_intent_statements():admin.execute(statement)
        conn.execute('SELECT public.prepare_capacity_occupation_account_guard(%s,%s)',(raw,Jsonb(source_ref))).fetchone()
    def probe(conn,body,target,judge):
        from aos_api.aip_eval_pack_registry import AipEvalPackRegistry
        fact=conn.execute('SELECT public.read_capacity_occupation_judge_fact(%s,%s,%s,%s,%s) AS fact',(raw,Jsonb(source_ref),UUID(judge.parent_limit.parent_hold_ref.resource_id),judge.request_id,judge.request_hash)).fetchone()['fact']
        ref=target.request.suite_ref
        row=conn.execute('SELECT * FROM aip_eval_suite_revision WHERE org_id=%s AND project_id=%s AND suite_id=%s AND revision=%s',('org-org','dev-project',ref.asset_id,ref.revision)).fetchone()
        suite=AipEvalPackRegistry._suite_from_row(row)
        suite_raw=json.dumps(suite.model_dump(mode='json',by_alias=True,exclude={'content_hash'}),ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
        assert len(suite.cases)==len(fact['application']['cases'])==2
        assert [c.case_id for c in suite.cases]==[c['caseId'] for c in fact['application']['cases']]
        assert target.parent_limit.upper_bound_minor==judge.parent_limit.upper_bound_minor==10
        trace=[]
        for case in suite.cases:
            for purpose,app in (('target',target),('judge',judge)):
                args=(raw,Jsonb(source_ref),UUID(app.parent_limit.parent_hold_ref.resource_id),app.request_id,app.request_hash,uuid4(),1)
                xid=conn.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid']
                try:
                    if purpose=='target':
                        debit=conn.execute('SELECT public.prepare_capacity_case_parent_debit(%s,%s,%s,%s,%s,%s,%s,%s,%s) AS debit',(*args,suite_raw,case.case_id)).fetchone()['debit']
                    else:
                        debit=conn.execute('SELECT public.prepare_capacity_judge_parent_debit(%s,%s,%s,%s,%s,%s,%s,%s) AS debit',(*args,case.case_id)).fetchone()['debit']
                except psycopg.errors.CheckViolation as error:
                    result=dict(xid=xid,source_ref=source_ref,source_limit=source.model_dump(mode='json',by_alias=True)['tokenLimit'],source_max_concurrency=source.max_concurrency,original_judge_fact=fact,successful_legs=trace,failed_leg=dict(case_id=case.case_id,purpose=purpose),sqlstate=error.sqlstate,error=str(error),per_parent_planned_minor=2,parent_caps=[10,10],planned_legs=4,whole_plan=body,execution_allowed=False,test_risk_not_real_price=True)
                    (Path(__file__).resolve().parent/'four-leg-red.json').write_text(json.dumps(result,indent=2)+'\n')
                    raise
                trace.append(dict(case_id=case.case_id,purpose=purpose,debit=debit))
        assert len(trace)==4,'complete original four-leg risk preparation required'
        return dict(all_four_original_legs_prepared=trace,execution_allowed=False)
    def finish(conn):
        xid=conn.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid']
        with pytest.raises(psycopg.errors.CheckViolation,match='CAPACITY_PARENT_FINALIZE_REQUIRED'):
            conn.commit()
        assert conn.info.transaction_status==psycopg.pq.TransactionStatus.IDLE
        return dict(xid=xid,actual_commit_rejected=True,sqlstate='23514',execution_allowed=False)
    trial_path=tmp_path/'source-newjudge';trial_path.mkdir()
    test_exact_signed_rule_new_original_suite(caller,issuer_factory,https_signer,
        guard_issuer_factory,guard_consumer_factory,trial_path,source_provider=provider,
        whole_caller_factory=native_factory,source_prefix=prefix,source_probe=probe,
        source_finish=finish if os.environ.get('AOS_NEW_JUDGE_INTENT_NATIVE') == '1' else None,
        source_native_only=os.environ.get('AOS_NEW_JUDGE_INTENT_NATIVE') == '1')

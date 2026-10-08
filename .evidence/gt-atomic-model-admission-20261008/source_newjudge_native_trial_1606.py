"""Owned integration: original signed Source and original new-Judge parent, no execution."""
from contextlib import contextmanager
import json
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
        conn.execute('SELECT public.prepare_capacity_occupation_account_guard(%s,%s)',(raw,Jsonb(source_ref))).fetchone()
    def probe(conn,body,target,judge):
        for case in body['cases']:
            for purpose in ('target','judge'):
                case[purpose]['sourceRef']=source_ref
                case[purpose]['physicalAccountRef']=source.account_candidate_ref.model_dump(mode='json',by_alias=True)
        parent=UUID(judge.parent_limit.parent_hold_ref.resource_id)
        args=(raw,Jsonb(source_ref),parent,judge.request_id,judge.request_hash)
        fact=conn.execute('SELECT public.read_capacity_occupation_judge_fact(%s,%s,%s,%s,%s) AS fact',args).fetchone()['fact']
        assert fact['purpose']=='model-judge-call' and fact['requestHash']==judge.request_hash
        assert fact['xid']==judge.caller_xid and fact['pid']==judge.caller_pid
        assert fact['application']['cases']==judge.request['cases'] and len(fact['application']['cases'])==2
        cases=[c['caseId'] for c in fact['application']['cases']]
        with conn.transaction(force_rollback=True):
            debit=uuid4()
            def allocate(key,minor,case):
                return conn.execute('SELECT public.prepare_capacity_judge_parent_debit(%s,%s,%s,%s,%s,%s,%s,%s) AS debit',(*args,key,minor,case)).fetchone()['debit']
            first=allocate(debit,10,cases[0]);replay=allocate(debit,10,cases[0])
            assert first==replay and first['allocatedMinor']==first['parentCapMinor']==10
            assert first['executionAllowed'] is False
            negatives=[]
            for key,minor,case,error in ((uuid4(),10,cases[0],'CAPACITY_JUDGE_CASE_ALLOCATION_CONFLICT'),(uuid4(),1,cases[1],'CAPACITY_PARENT_CAP_EXCEEDED')):
                with conn.transaction(force_rollback=True):
                    with pytest.raises(psycopg.errors.CheckViolation,match=error):allocate(key,minor,case)
                negatives.append(error)
            with conn.transaction(force_rollback=True):
                with pytest.raises(psycopg.errors.CheckViolation,match='CAPACITY_PARENT_FINALIZE_REQUIRED'):
                    conn.execute('SET CONSTRAINTS ALL IMMEDIATE')
            negatives.append('CAPACITY_PARENT_FINALIZE_REQUIRED')
        result=dict(source_ref=source_ref,account_ref=source.account_candidate_ref.model_dump(mode='json',by_alias=True),
            original_fact=fact,prepared_debit=first,exact_replay=True,negative_cases=negatives,
            actual_scram=True,whole_commit=False,execution_allowed=False,
            remaining='four-leg allocation, original input dependency, Intent, finalizer, transport and Usage')
        (base/'source-newjudge-native-positive-1606.json').write_text(json.dumps(result,indent=2)+'\n')
        return result
    trial_path=tmp_path/'source-newjudge';trial_path.mkdir()
    test_exact_signed_rule_new_original_suite(caller,issuer_factory,https_signer,
        guard_issuer_factory,guard_consumer_factory,trial_path,source_provider=provider,
        whole_caller_factory=native_factory,source_prefix=prefix,source_probe=probe)

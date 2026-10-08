"""Owned integration: original signed Source and original new-Judge parent, no execution."""
from contextlib import contextmanager
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
        with conn.transaction(force_rollback=os.environ.get('AOS_NEW_JUDGE_INTENT_NATIVE') != '1'):
            debit=uuid4()
            def allocate(key,minor,case):
                return conn.execute('SELECT public.prepare_capacity_judge_parent_debit(%s,%s,%s,%s,%s,%s,%s,%s) AS debit',(*args,key,minor,case)).fetchone()['debit']
            first=allocate(debit,10,cases[0]);replay=allocate(debit,10,cases[0])
            assert first==replay and first['allocatedMinor']==first['parentCapMinor']==10
            assert first['executionAllowed'] is False
            intent_proof=None
            if os.environ.get('AOS_NEW_JUDGE_INTENT_NATIVE') == '1':
                from aos_api.aip_eval_pack_registry import AipEvalPackRegistry
                from aos_api.ecommerce_content_pre_review_pack import build_content_pre_review_eval_packs
                from aos_api.ecommerce_content_pre_review_eval import GRAPH_ID,build_content_pre_review_graph
                from aos_api.aip_eval_contracts import AssetRevisionRef,AssetType
                from aos_api.aip_logic_graph_models import compute_logic_graph_hash
                ref=target.request.suite_ref
                suite_row=conn.execute('SELECT * FROM aip_eval_suite_revision WHERE org_id=%s AND project_id=%s AND suite_id=%s AND revision=%s',('org-org','dev-project',ref.asset_id,ref.revision)).fetchone()
                suite=AipEvalPackRegistry._suite_from_row(suite_row)
                suite_raw=json.dumps(suite.model_dump(mode='json',by_alias=True,exclude={'content_hash'}),ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
                original_target=AssetRevisionRef(assetType=AssetType.LOGIC_GRAPH,assetId=GRAPH_ID,revision='1',contentHash=compute_logic_graph_hash(build_content_pre_review_graph()))
                _,pack=build_content_pre_review_eval_packs(original_target)
                input_ref=suite.cases[0].input_artifact
                input_raw=json.dumps(pack.artifacts[(input_ref.artifact_id,input_ref.revision)],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
                target_id=uuid4();target_debit=uuid4()
                target_args=(raw,Jsonb(source_ref),UUID(target.parent_limit.parent_hold_ref.resource_id),target.request_id,target.request_hash,target_debit,1,suite_raw,cases[0],input_raw,target_id)
                target_intent=conn.execute('SELECT public.prepare_capacity_execution_intent(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) AS intent',target_args).fetchone()['intent']
                judge_id=uuid4()
                def prepare_judge(key=judge_id,producer=target_id,case=cases[0]):
                    return conn.execute('SELECT public.prepare_capacity_judge_execution_intent(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) AS intent',(*args,debit,10,case,producer,key)).fetchone()['intent']
                intent=prepare_judge();assert intent==prepare_judge()
                assert intent['state']=='awaiting_target_result' and intent['executionAllowed'] is False
                approval=fact['approvalSnapshot']
                assert intent['immutable']['proposalId']==approval['proposal_id']
                assert intent['immutable']['proposalHash']==approval['proposal_hash'] and approval['proposal_hash']
                assert intent['immutable']['approvalIdempotencyKey']==approval['idempotency_key'] and approval['idempotency_key']
                assert intent['immutable']['targetIntentHash']==target_intent['contentHash']
                assert intent['immutable']['debitHash']==first['contentHash']
                dependency=intent['immutable']['inputDependency']
                assert dependency['protocol']=='aos.model-eval-judge-input/v1' and dependency['state']=='awaiting_target_result'
                assert dependency['expectedArtifact']==fact['application']['cases'][0]['expectedArtifact']
                intent_negatives=[]
                for changed,error in ((dict(key=uuid4()),'REPLAY_CONFLICT'),(dict(producer=uuid4()),'ORIGINAL_TARGET_REQUIRED'),(dict(case=cases[1]),'ORIGINAL_TARGET_REQUIRED'),(dict(key=None),'ID_REQUIRED')):
                    with conn.transaction(force_rollback=True):
                        with pytest.raises(psycopg.errors.CheckViolation,match=error):prepare_judge(**changed)
                    intent_negatives.append(error)
                with conn.transaction(force_rollback=True):
                    with pytest.raises(psycopg.errors.InsufficientPrivilege):
                        conn.execute('SELECT * FROM aos_physical_capacity_occupation_private.prepared_judge_intent')
                intent_proof=dict(target=target_intent,judge=intent,exact_replay=True,negative_cases=intent_negatives,actual_target_output_present=False,execution_allowed=False)
                (base/'newjudge-pending-intent-native-1607.json').write_text(json.dumps(intent_proof,indent=2)+'\n')
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
        if intent_proof is not None:result['pending_judge_intent']=intent_proof
        label=os.environ.get('AOS_SOURCE_NEWJUDGE_PROOF','source-newjudge-native-positive-1606.json')
        (base/label).write_text(json.dumps(result,indent=2)+'\n')
        return result
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

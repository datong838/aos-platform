"""Fresh original Source + complete dual-parent native risk bridge trial."""
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4
import copy
import json
import os
import psycopg
import pytest
from psycopg.rows import dict_row
from aos_api.tenant_scope import apply_transaction_scope, TenantScope
from tests.aip._runtime_guard_history_fixture import isolated_owner

POLICY = None

def run_source_newjudge_trial(params, command, exact, source, provider, caller,
        issuer_factory, https_signer, guard_issuer_factory, guard_consumer_factory, tmp_path, base):
    from aos_api.aip_physical_capacity_occupation_authority import (
        occupation_judge_fact_statements, occupation_judge_parent_debit_statements,
        occupation_plan_risk_statements, occupation_shared_risk_description_statements)
    from aos_api.aip_provider_capacity_source_consumer import _consumption_packet
    from psycopg.types.json import Jsonb
    from aos_api.aip_physical_capacity_occupation import prepare_shared_parent_risk_plan, prepare_shared_parent_risk_description
    from aos_api.aip_model_eval_execution_owner import ModelEvalOwnerRejected
    from tests.aip.test_model_eval_judge_authority_pg import test_exact_signed_rule_new_original_suite
    # Reuse the current original test unchanged: its fresh approval window is
    # 150 seconds. Never extend an existing approval or replay r1 effects.
    import inspect,hashlib
    original_text=inspect.getsource(test_exact_signed_rule_new_original_suite)
    assert original_text.count('expires=datetime.now(UTC)+timedelta(seconds=150)')==1
    Path(__file__).with_name('approval-window-origin.json').write_text(json.dumps({
        'original_function_sha256':hashlib.sha256(original_text.encode()).hexdigest(),
        'original_test_used_unchanged':True,'current_fresh_approval_seconds':150,
        'clock_mocked':False,'previous_expired_approval_extended':False},indent=2)+'\n')
    proofs = []
    def install_before_snapshot():
        from aos_api import aip_shared_parent_atomic_admission as admission
        from aos_api.aip_physical_capacity_occupation_authority import OWNER
        with isolated_owner() as admin:
            for statement in (*occupation_judge_fact_statements(),
                              *occupation_judge_parent_debit_statements(),
                              *occupation_plan_risk_statements(),
                              *occupation_shared_risk_description_statements()):
                admin.execute(statement)
        with isolated_owner() as admin:
            for statement in (*admission.shared_parent_original_fact_statements(), *admission.shared_parent_admission_origin_statements()):
                admin.execute(statement)
            # Explicit test-only forwarding proxy. No original production
            # function is replaced and no formal/retained old DB is used.
            admin.execute("""CREATE FUNCTION public.test_owned_versioned_origin(
              p_raw bytea,p_source jsonb,p_target uuid,p_tr text,p_th text,
              p_judge uuid,p_jr text,p_jh text,p_plan uuid,p_manifest jsonb,p_hash text)
              RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $proxy$
              DECLARE before_counts jsonb; after_counts jsonb; result jsonb;
              BEGIN
                before_counts:=jsonb_build_array(
                  (SELECT count(*) FROM aos_physical_capacity_occupation_private.prepared_plan_risk),
                  (SELECT count(*) FROM aos_physical_capacity_occupation_private.prepared_shared_risk_description));
                result:=public.build_shared_parent_admission_origin(p_raw,p_source,p_target,p_tr,p_th,p_judge,p_jr,p_jh,p_plan,p_manifest,p_hash);
                after_counts:=jsonb_build_array(
                  (SELECT count(*) FROM aos_physical_capacity_occupation_private.prepared_plan_risk),
                  (SELECT count(*) FROM aos_physical_capacity_occupation_private.prepared_shared_risk_description));
                IF before_counts IS DISTINCT FROM after_counts THEN RAISE EXCEPTION 'LEGACY_PREPARATION_MUTATED'; END IF;
                RETURN result||jsonb_build_object('legacyBefore',before_counts,'legacyAfter',after_counts);
              END $proxy$""")
            signature='public.test_owned_versioned_origin(bytea,jsonb,uuid,text,text,uuid,text,text,uuid,jsonb,text)'
            admin.execute('ALTER FUNCTION '+signature+' OWNER TO '+OWNER)
            admin.execute('REVOKE ALL ON FUNCTION '+signature+' FROM PUBLIC')
            admin.execute('GRANT EXECUTE ON FUNCTION '+signature+' TO aos_runtime')
    @contextmanager
    def native_factory(scope):
        install_before_snapshot()
        with psycopg.connect(**params, row_factory=dict_row) as conn:
            conn.isolation_level = psycopg.IsolationLevel.SERIALIZABLE
            conn.execute("SET LOCAL TimeZone='UTC'")
            apply_transaction_scope(conn, scope)
            yield conn
    def prefix(conn):
        conn.execute('SELECT public.prepare_capacity_occupation_account_guard(%s,%s::jsonb)',
            (_consumption_packet(command), Jsonb(exact.model_dump(mode='json', by_alias=True))))
    def probe(conn, body, target, judge):
        from aos_api import aip_shared_parent_atomic_admission as admission
        from aos_api.aip_physical_capacity_occupation_authority import OWNER
        from aos_api.aip_model_runtime_store import canonical_hash
        from uuid import UUID
        shared=copy.deepcopy(body)
        shared['schemaVersion']='aos.model-eval-target-judge-shared-risk-manifest/v3'
        shared['executionId']=str(uuid4())
        for case in shared['cases']:
            for purpose in ('target','judge'):
                case[purpose]['sourceRef']=exact.model_dump(mode='json',by_alias=True)
                case[purpose]['physicalAccountRef']=source.account_candidate_ref.model_dump(mode='json',by_alias=True)
                del case[purpose]['allocationUpperBoundMinor'];del case[purpose]['budgetAllocationRef']
        params_origin=(_consumption_packet(command),Jsonb(exact.model_dump(mode='json',by_alias=True)),
            UUID(target.parent_limit.parent_hold_ref.resource_id),target.request_id,target.request_hash,
            UUID(judge.parent_limit.parent_hold_ref.resource_id),judge.request_id,judge.request_hash,
            UUID(shared['executionId']))
        def build(value=shared, hash_override=None):
            return conn.execute('SELECT public.test_owned_versioned_origin(%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s) AS doc',
                (*params_origin,Jsonb(value),canonical_hash(value) if hash_override is None else hash_override)).fetchone()['doc']
        caller_origin=conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
        doc=build();assert doc==build()
        assert doc['immutable']['callerXid']==caller_origin['xid'] and doc['immutable']['callerPid']==caller_origin['pid']
        assert doc['contentHash']=='sha256:'+canonical_hash(doc['immutable'])
        assert doc['immutable']['originalRiskHash']=='sha256:'+canonical_hash(doc['immutable']['originalRisk'])
        assert doc['immutable']['manifest']==shared and doc['immutable']['state']=='awaiting_full_admission'
        assert doc['executionAllowed'] is False and doc['legacyBefore']==doc['legacyAfter']
        failures=[]
        for field in ('sourceRef','physicalAccountRef','budgetHoldRef','approvalRef'):
            bad=copy.deepcopy(shared)
            key='assetId' if field in ('sourceRef','physicalAccountRef') else 'resourceId'
            bad['cases'][-1]['judge'][field][key]+='-wrong'
            with pytest.raises(psycopg.errors.CheckViolation):
                with conn.transaction(): build(bad)
            failures.append(field)
        with pytest.raises(psycopg.errors.CheckViolation):
            with conn.transaction(): build(hash_override='0'*64)
        assert build()==doc
        proofs.append(dict(origin=doc,caller=caller_origin,negative_cases=failures+['manifestHash'],
            original_signed_source_and_independent_parents=True,legacy_preparation_unchanged=True,
            execution_allowed=False,full_admission_pass=False))
        return proofs[-1]
    def finish(conn):
        xid=conn.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid']
        conn.rollback()
        assert conn.info.transaction_status==psycopg.pq.TransactionStatus.IDLE
        proofs[0]['rollback_xid']=xid
        return dict(xid=xid,rollback=True,commit_attempted=False,execution_allowed=False)
    trial_path = tmp_path / 'shared-parent-native-source'
    trial_path.mkdir()
    test_exact_signed_rule_new_original_suite(caller, issuer_factory, https_signer,
        guard_issuer_factory, guard_consumer_factory, trial_path, source_provider=provider,
        whole_caller_factory=native_factory, source_prefix=prefix, source_probe=probe,
        source_finish=finish, source_native_only=True)
    assert len(proofs) == 1
    with Path(__file__).with_name('native-origin-proof.json').open('x') as stream:
        json.dump(proofs[0], stream, ensure_ascii=False, indent=2)

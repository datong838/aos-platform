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
        occupation_plan_risk_statements)
    from aos_api.aip_provider_capacity_source_consumer import _consumption_packet
    from psycopg.types.json import Jsonb
    from aos_api.aip_physical_capacity_occupation import prepare_shared_parent_risk_plan
    from aos_api.aip_model_eval_execution_owner import ModelEvalOwnerRejected
    from tests.aip.test_model_eval_judge_authority_pg import test_exact_signed_rule_new_original_suite
    proofs = []
    @contextmanager
    def native_factory(scope):
        with psycopg.connect(**params, row_factory=dict_row) as conn:
            conn.isolation_level = psycopg.IsolationLevel.SERIALIZABLE
            conn.execute("SET LOCAL TimeZone='UTC'")
            apply_transaction_scope(conn, scope)
            yield conn
    def prefix(conn):
        with isolated_owner() as admin:
            for statement in (*occupation_judge_fact_statements(),
                              *occupation_judge_parent_debit_statements(),
                              *occupation_plan_risk_statements()):
                admin.execute(statement)
        conn.execute('SELECT public.prepare_capacity_occupation_account_guard(%s,%s::jsonb)',
            (_consumption_packet(command), Jsonb(exact.model_dump(mode='json', by_alias=True))))
    def probe(conn, body, target, judge):
        # Keep original v2 caller input; only Source/account descriptions are
        # set to this actual fresh Source, as in its existing original trial.
        for case in body['cases']:
            for purpose in ('target', 'judge'):
                case[purpose]['sourceRef'] = exact.model_dump(mode='json', by_alias=True)
                case[purpose]['physicalAccountRef'] = source.account_candidate_ref.model_dump(mode='json', by_alias=True)
        shared = copy.deepcopy(body)
        shared['schemaVersion'] = 'aos.model-eval-target-judge-shared-risk-manifest/v3'
        shared['executionId'] = str(uuid4())
        for case in shared['cases']:
            for purpose in ('target', 'judge'):
                del case[purpose]['allocationUpperBoundMinor']
                del case[purpose]['budgetAllocationRef']
        assert POLICY is not None
        def prepare(value=shared):
            return prepare_shared_parent_risk_plan(conn, TenantScope('org-org', 'dev-project'),
                command, value, **POLICY)
        result = prepare()
        assert result == prepare()
        assert len(result['immutable']['legs']) == 4
        assert result['physicalPreparedRequests'] == result['physicalPreparedTokens'] == 0
        assert [r['upperBoundMinor'] for r in result['immutable']['parentRisks']] == [10, 10]
        faults = []
        for fault in ('source', 'money', 'old_domain', 'plan_id'):
            value = copy.deepcopy(shared)
            if fault == 'source': value['cases'][0]['judge']['sourceRef']['assetId'] = 'unbound-source'
            elif fault == 'money': value['cases'][0]['target']['allocationUpperBoundMinor'] = 1
            elif fault == 'old_domain': value = body
            elif fault == 'plan_id': value['executionId'] = str(uuid4())
            with conn.transaction(force_rollback=True):
                with pytest.raises(ModelEvalOwnerRejected): prepare(value)
            faults.append(fault)
        with conn.transaction(force_rollback=True):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute('SELECT * FROM aos_physical_capacity_occupation_private.prepared_plan_risk')
        with conn.transaction(force_rollback=True):
            with pytest.raises(psycopg.errors.CheckViolation, match='CAPACITY_PARENT_FINALIZE_REQUIRED'):
                conn.execute('SET CONSTRAINTS ALL IMMEDIATE')
        proofs.append(dict(plan=result, manifest=shared, negative_cases=faults,
            private_read_denied=True, early_finalize_denied=True, execution_allowed=False))
        return proofs[-1]
    def finish(conn):
        xid = conn.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid']
        with pytest.raises(psycopg.errors.CheckViolation, match='CAPACITY_PARENT_FINALIZE_REQUIRED'):
            conn.commit()
        assert conn.info.transaction_status == psycopg.pq.TransactionStatus.IDLE
        proofs[0]['actual_commit_rejected'] = True
        proofs[0]['xid'] = xid
        return dict(xid=xid, actual_commit_rejected=True, execution_allowed=False)
    trial_path = tmp_path / 'shared-parent-native-source'
    trial_path.mkdir()
    test_exact_signed_rule_new_original_suite(caller, issuer_factory, https_signer,
        guard_issuer_factory, guard_consumer_factory, trial_path, source_provider=provider,
        whole_caller_factory=native_factory, source_prefix=prefix, source_probe=probe,
        source_finish=finish, source_native_only=True)
    assert len(proofs) == 1
    with Path(__file__).with_name('native-risk-binding-proof.json').open('x') as stream:
        json.dump(proofs[0], stream, ensure_ascii=False, indent=2)

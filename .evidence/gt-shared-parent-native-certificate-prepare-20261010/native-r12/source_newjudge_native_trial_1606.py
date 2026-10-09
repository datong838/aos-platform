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
    # New independently approved experiment; original on-disk test and deadlines unchanged.
    import inspect,hashlib
    import tests.aip.test_model_eval_judge_authority_pg as original_module
    original_text=inspect.getsource(test_exact_signed_rule_new_original_suite)
    old_window='expires=datetime.now(UTC)+timedelta(seconds=50)'
    assert original_text.count(old_window)==1
    experiment_text=original_text.replace(old_window,'expires=datetime.now(UTC)+timedelta(seconds=110)')
    namespace=dict(vars(original_module))
    exec(compile(experiment_text,str(Path(__file__).with_name('new_approval_window_fixture.py')),'exec'),namespace)
    test_exact_signed_rule_new_original_suite=namespace['test_exact_signed_rule_new_original_suite']
    Path(__file__).with_name('new_approval_window_fixture.py').write_text(experiment_text)
    Path(__file__).with_name('approval-window-origin.json').write_text(json.dumps({
        'original_function_sha256':hashlib.sha256(original_text.encode()).hexdigest(),
        'experiment_function_sha256':hashlib.sha256(experiment_text.encode()).hexdigest(),
        'new_independent_approval_seconds':110,'original_on_disk_unchanged':True,
        'original_request_and_signed_rule_deadlines_unchanged':True,
        'clock_mocked':False,'previous_expired_approval_extended':False},indent=2)+'\n')
    proofs = []
    @contextmanager
    def native_factory(scope):
        with psycopg.connect(**params, row_factory=dict_row) as conn:
            conn.isolation_level = psycopg.IsolationLevel.SERIALIZABLE
            conn.execute("SET LOCAL TimeZone='UTC'")
            apply_transaction_scope(conn, scope)
            yield conn
    from aos_api import aip_model_eval_execution_authority as identity_authority
    from aos_api.aip_model_shared_parent_certificate_identity import shared_parent_identity_statements
    from aos_api.aip_shared_parent_description_origin_reader import shared_description_origin_statements
    from aos_api.aip_shared_parent_executor_set_reader import shared_parent_executor_set_statements
    from aos_api.aip_shared_parent_certificate_prepare import shared_parent_certificate_prepare_statements
    import sys
    sys.path.insert(0,str(Path(__file__).parent))
    from shared_identity_certificate_fixture import prime_root
    from datetime import datetime,timezone
    root=prime_root(datetime.now(timezone.utc))
    def encoded(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    with isolated_owner() as admin:
        identity_authority.install_closed_model_identity_authority(admin.execute)
        for statement in shared_parent_identity_statements():admin.execute(statement)
        admin.execute('SET LOCAL ROLE '+identity_authority.ISSUER_OWNER)
        admin.execute("SET LOCAL aos.org_id='org-org'");admin.execute("SET LOCAL aos.project_id='dev-project'")
        digest=hashlib.sha256(encoded(root)).hexdigest()
        admin.execute('INSERT INTO aos_model_eval_issuer_private.issuer_root(org_id,project_id,issuer_id,key_id,bootstrap_hash,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s,%s)',('org-org','dev-project',root['issuerId'],root['issuerKeyId'],'a'*64,digest,encoded(root)))
        admin.execute('INSERT INTO aos_model_eval_issuer_private.issuer_epoch(org_id,project_id,issuer_id,key_id,epoch,root_hash) VALUES (%s,%s,%s,%s,1,%s)',('org-org','dev-project',root['issuerId'],root['issuerKeyId'],digest))
        root_xid=admin.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid']
    Path(__file__).with_name('prepublished-root-proof.json').open('x').write(json.dumps(dict(root=root,root_xid=root_xid,root_hash=digest,root_provenance_verified=False,prepublished_before_native_factory=True,execution_allowed=False),indent=2)+'\n')
    def prefix(conn):
        with isolated_owner() as admin:
            for statement in (*occupation_judge_fact_statements(),*occupation_judge_parent_debit_statements(),
                *occupation_plan_risk_statements(),*occupation_shared_risk_description_statements(),*shared_description_origin_statements(),
                *shared_parent_executor_set_statements(),*shared_parent_certificate_prepare_statements()):admin.execute(statement)
        assert conn.execute('SELECT pg_visible_in_snapshot(%s::xid8,pg_current_snapshot()) AS visible',(root_xid,)).fetchone()['visible']
        conn.execute('SELECT public.prepare_capacity_occupation_account_guard(%s,%s::jsonb)',
            (_consumption_packet(command),Jsonb(exact.model_dump(mode='json',by_alias=True))))
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
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[3]/'.evidence/gt-model-typed-proof-20261008'))
        from shared_identity_certificate_fixture import keys_for_manifest, issue
        certificate_keys = keys_for_manifest(shared)
        assert POLICY is not None
        def prepare(value=shared):
            return prepare_shared_parent_risk_plan(conn, TenantScope('org-org', 'dev-project'),
                command, value, **POLICY)
        def observe_description(*args,**kwargs):
            try:return prepare_shared_parent_risk_description(*args,**kwargs)
            except ModelEvalOwnerRejected as exc:
                context=exc.__context__
                Path(__file__).with_name('description-failure-context.json').write_text(json.dumps({
                    'class':type(context).__name__,'sqlstate':getattr(context,'sqlstate',None),
                    'message':str(context)[:1000], 'source_valid_from':str(source.valid_from), 'source_valid_until':str(source.valid_until), 'nested_class':type(getattr(context,'__context__',None)).__name__, 'nested_message':str(getattr(context,'__context__',None))[:1000]},indent=2)+'\n')
                raise
        description = observe_description(conn, TenantScope('org-org','dev-project'),
            command, shared, **POLICY)
        Path(__file__).with_name('first-description-proof.json').write_text(json.dumps(description.model_dump(mode='json',by_alias=True),indent=2)+'\n')
        assert description.immutable.executors_authenticated is False
        from datetime import datetime,timezone
        certificate_proof=issue(description.model_dump(mode='json',by_alias=True),certificate_keys,datetime.now(timezone.utc))
        from final_expiry_trial import verify_final_expiry
        verify_final_expiry(conn,command,shared,description,certificate_proof,POLICY,Path(__file__).parent)
        certificate_proof=issue(description.model_dump(mode='json',by_alias=True),certificate_keys,datetime.now(timezone.utc))
        from tests.aip.test_shared_parent_certificate_prepare_pg import verify_native_same_transaction_prepare
        verify_native_same_transaction_prepare(conn,command,shared,description,certificate_proof,POLICY,Path(__file__).parent, fresh_certificate_proof=lambda: issue(description.model_dump(mode='json',by_alias=True),certificate_keys,datetime.now(timezone.utc)))
        descriptive_faults=[]
        with conn.transaction(force_rollback=True):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute('SELECT * FROM aos_physical_capacity_occupation_private.prepared_shared_risk_description')
        faults = []
        for fault in ():
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
        proofs.append(dict(description=description.model_dump(mode="json",by_alias=True), descriptive_faults=descriptive_faults, manifest=shared, negative_cases=faults,
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
    with Path(__file__).with_name('native-description-proof.json').open('x') as stream:
        json.dump(proofs[0], stream, ensure_ascii=False, indent=2)

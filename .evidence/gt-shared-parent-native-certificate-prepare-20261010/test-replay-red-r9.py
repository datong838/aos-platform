"""Signed staging is not execution or issuer-root bootstrap authority."""
import re
from aos_api import aip_shared_parent_certificate_prepare as api


def test_artifact_keeps_closed_root_and_direct_table_permissions():
    sql = '\n'.join(api.shared_parent_certificate_prepare_statements())
    assert 'SECURITY DEFINER SET search_path=pg_catalog' in sql
    assert "session_user<>'aos_provider_capacity_occupation'" in sql
    assert "'serializable'" in sql and "'aos_runtime'" in sql
    assert 'read_capacity_shared_risk_description_origin' in sql
    assert 'aos_ed25519.verify' in sql and "'$libdir/aos_ed25519'" in sql
    assert 'require_current_source_installation()' in sql
    assert 'verify_model_shared_parent_certificate_signature' in sql
    assert 'GRANT USAGE ON SCHEMA aos_ed25519' not in sql
    assert 'GRANT EXECUTE ON FUNCTION aos_ed25519.verify' not in sql
    assert 'AOS-MODEL-EVAL-SHARED-PARENT-CERTIFICATE-SIGNING-INPUT-v3' in sql
    for field in ('descriptionHash', 'originalRiskHash', 'callerXid', 'callerPid', 'manifestHash'):
        assert field in sql
    assert 'shared_parent_certificate_identity_binding' in sql
    assert not re.search(r'INSERT\s+INTO[^;]*\.issuer_root', sql, re.I)
    assert not re.search(r'GRANT\s+(INSERT|UPDATE|DELETE|SELECT|ALL)\s+ON\s+(TABLE\s+)?[^;]+', sql, re.I)
    assert 'COMMIT' not in sql and 'executionAllowed' in sql and 'false' in sql


def test_wrapper_does_not_repair_roles_or_commit_outer_transaction():
    import inspect
    source=inspect.getsource(api.prepare_shared_parent_certificate_set)
    assert 'with conn.transaction()' in source
    assert 'read_shared_parent_executor_set' in source
    assert '.commit(' not in source and 'SET ROLE' not in source and 'RESET ROLE' not in source


def verify_native_same_transaction_prepare(conn, command, manifest, description, proof, policy, evidence_dir, *, fresh_certificate_proof=None):
    import base64,copy,json
    from pathlib import Path
    import psycopg,pytest
    from psycopg.types.json import Jsonb
    from aos_api.tenant_scope import TenantScope
    from aos_api.aip_provider_capacity_source_consumer import _consumption_packet
    scope=TenantScope('org-org','dev-project')
    args=dict(expected_content_hash=description.content_hash,**policy)
    certificates=proof['certificates']
    def encode(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    packet=_consumption_packet(command)
    source=Jsonb(command.source_ref.model_dump(mode='json',by_alias=True))
    negatives=[]
    faults={}
    bad=copy.deepcopy(certificates);bad[0]['signatureBase64']=base64.b64encode(bytes(64)).decode();faults['bad_signature']=encode(bad)
    bad=copy.deepcopy(certificates);bad[0]['certificate']['callerXid']=str(int(description.immutable.caller_xid)+1);faults['other_origin']=encode(bad)
    faults['missing_leg']=encode(certificates[:-1]);faults['duplicate_leg']=encode(certificates[:-1]+[certificates[0]])
    faults['noncanonical_bytes']=json.dumps(certificates,indent=2).encode()
    for name,raw in faults.items():
        with pytest.raises(psycopg.errors.CheckViolation) as rejected:
            with conn.transaction():
                conn.execute('SELECT public.prepare_model_shared_parent_certificate_set(%s,%s::jsonb,%s::uuid,%s,%s)',
                    (packet,source,description.plan_id,description.content_hash,raw))
        if name=='bad_signature':assert rejected.value.diag.message_primary=='SHARED_CERTIFICATE_SIGNATURE_OR_TIME_REQUIRED'
        with pytest.raises(psycopg.errors.CheckViolation,match='SHARED_EXECUTOR_MANIFEST_REQUIRED'):
            with conn.transaction():
                conn.execute('SELECT public.read_model_shared_parent_executor_set_facts(%s,%s,%s,%s)',
                    (manifest['executionId'],description.immutable.manifest_hash,description.content_hash,description.immutable.original_risk_hash))
        negatives.append(dict(name=name,sqlstate=rejected.value.sqlstate,message=rejected.value.diag.message_primary))
    cleanup=None
    if fresh_certificate_proof is not None:
        from aos_api.aip_model_eval_execution_owner import ModelEvalOwnerRejected
        certificates=fresh_certificate_proof()['certificates']
        reached=[]
        def postwrite_failure(*unused,**ignored):
            reached.append(True)
            raise ModelEvalOwnerRejected('ISOLATED_POSTWRITE_FAILURE')
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(api,'read_shared_parent_executor_set',postwrite_failure)
            with pytest.raises(ModelEvalOwnerRejected,match='SHARED_CERTIFICATE_NATIVE_PREPARATION_REQUIRED'):
                api.prepare_shared_parent_certificate_set(conn,scope,command,manifest,certificates,**args)
        assert reached==[True]  # The real SQL staging completed before the fault.
        with pytest.raises(psycopg.errors.CheckViolation,match='SHARED_EXECUTOR_MANIFEST_REQUIRED'):
            with conn.transaction():
                conn.execute('SELECT public.read_model_shared_parent_executor_set_facts(%s,%s,%s,%s)',
                    (manifest['executionId'],description.immutable.manifest_hash,description.content_hash,description.immutable.original_risk_hash))
        cleanup=dict(actual_sql_staging_completed=True,caught_python_failure=True,
            same_caller_manifest_absent=True,outer_transaction_still_live=True)
        certificates=fresh_certificate_proof()['certificates']
    result=api.prepare_shared_parent_certificate_set(conn,scope,command,manifest,certificates,**args)
    assert result['description']==description and result['execution_allowed'] is False
    assert result['root_provenance_verified'] is False
    metadata=result['metadata']
    assert len(metadata['certificates'])==len(manifest['cases'])*2
    # Actual same-caller original metadata, not an epoch-only projection.
    versions=[item['identityVersion'] for item in metadata['certificates']]
    assert all(type(v) is int and v>=1 for v in versions)
    original_certificates=[json.loads(base64.b64decode(item['certificateBody'],validate=True))
        for item in metadata['certificates']]
    replay=conn.execute('SELECT public.prepare_model_shared_parent_certificate_set(%s,%s::jsonb,%s::uuid,%s,%s) AS fact',
        (packet,source,description.plan_id,description.content_hash,encode(original_certificates))).fetchone()['fact']
    assert replay['executionAllowed'] is False and replay['rootProvenanceVerified'] is False
    assert replay['metadata']['certificates']==metadata['certificates']
    boundaries=[]
    with pytest.raises(psycopg.errors.InsufficientPrivilege,match='SHARED_CERTIFICATE_NATIVE_CALLER_REQUIRED'):
        with conn.transaction():
            conn.execute("SET LOCAL aos.org_id='dev-org'")
            conn.execute('SELECT public.prepare_model_shared_parent_certificate_set(%s,%s::jsonb,%s::uuid,%s,%s)',
                (packet,source,description.plan_id,description.content_hash,encode(original_certificates)))
    boundaries.append('canary_scope_before_writes')
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with conn.transaction():
            conn.execute('SELECT public.verify_model_shared_parent_certificate_signature(%s,%s,%s)',
                (bytes(64),b'AOS-MODEL-EVAL-SHARED-PARENT-CERTIFICATE-SIGNING-INPUT-v3\n{}',bytes(32)))
    boundaries.append('runtime_direct_verifier_denied')
    after=conn.execute('SELECT public.read_model_shared_parent_executor_set_facts(%s,%s,%s,%s) AS fact',
        (manifest['executionId'],description.immutable.manifest_hash,description.content_hash,description.immutable.original_risk_hash)).fetchone()['fact']
    assert after['certificates']==metadata['certificates']
    assert (after['callerXid'],after['callerPid'])==(metadata['callerXid'],metadata['callerPid'])
    replay_verification=dict(identity_versions_before=versions,
        identity_versions_after=[item['identityVersion'] for item in after['certificates']],
        same_original_certificate_set_replayed=True,boundaries_rejected=boundaries,
        same_caller_and_current_metadata_unchanged=True)
    assert (metadata['callerXid'],metadata['callerPid'])==(description.immutable.caller_xid,description.immutable.caller_pid)
    with conn.transaction(force_rollback=True):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute('SELECT * FROM aos_model_eval_issuer_private.executor_certificate')
    (Path(evidence_dir)/'native-same-transaction-prepare-proof.json').open('x').write(json.dumps(dict(
        exact_original_description_hash=description.content_hash,native_caller=dict(xid=metadata['callerXid'],pid=metadata['callerPid']),
        certificate_count=len(metadata['certificates']),metadata=metadata,negative_cases=negatives,postwrite_savepoint_cleanup=cleanup,replay_verification=replay_verification,
        same_native_caller_observed=True,root_provenance_verified=False,execution_allowed=False,full_task_delivered=False),indent=2,default=str)+'\n')

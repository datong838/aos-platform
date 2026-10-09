"""Original v3 metadata in the physical caller; no trusted root or execution."""
import base64
import hashlib
import re

import psycopg
from psycopg.rows import dict_row

from aos_api.aip_model_eval_execution_authority import ISSUER_OWNER, ISSUER_SCHEMA, SCHEMA
from aos_api.aip_model_eval_execution_contracts import (
    ModelEvalIssuerVerificationInput, ModelSharedParentRiskSignedCertificateEnvelope,
    validate_shared_parent_certificate_signature,
)
from aos_api.aip_model_eval_execution_owner import ModelEvalOwnerRejected
from aos_api.aip_model_runtime_store import canonical_hash
from aos_api.aip_shared_parent_description_origin_reader import read_shared_parent_description_origin

FUNCTION = 'public.read_model_shared_parent_executor_set_facts(text,text,text,text)'


def shared_parent_executor_set_statements():
    """Explicit isolated bridge; original metadata locks, never table grants."""
    s = ISSUER_SCHEMA
    return (
        f'''CREATE FUNCTION {FUNCTION.split('(')[0]}(
          p_execution text,p_manifest_hash text,p_description_hash text,p_risk_hash text)
          RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $shared$
          DECLARE p record; r record; h record; packed jsonb; expected integer; actual integer; unique_count integer;
          BEGIN
            IF session_user<>'aos_provider_capacity_occupation'
              OR current_setting('role',true) IS DISTINCT FROM 'aos_runtime'
              OR current_setting('transaction_isolation') IS DISTINCT FROM 'serializable'
              OR current_setting('transaction_read_only') IS DISTINCT FROM 'off'
              OR current_setting('TimeZone') IS DISTINCT FROM 'UTC'
              OR current_setting('session_replication_role') IS DISTINCT FROM 'origin'
              OR current_setting('aos.org_id',true) IS DISTINCT FROM 'org-org'
              OR current_setting('aos.project_id',true) IS DISTINCT FROM 'dev-project'
              OR p_execution IS NULL OR length(p_execution) NOT BETWEEN 1 AND 200
              OR p_execution IS DISTINCT FROM btrim(p_execution)
              OR p_manifest_hash IS NULL OR p_manifest_hash !~ '^[0-9a-f]{{64}}$'
              OR p_description_hash IS NULL OR p_description_hash !~ '^sha256:[0-9a-f]{{64}}$'
              OR p_risk_hash IS NULL OR p_risk_hash !~ '^sha256:[0-9a-f]{{64}}$' THEN
              RAISE EXCEPTION 'SHARED_EXECUTOR_NATIVE_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
            SELECT * INTO p FROM {SCHEMA}.manifest WHERE org_id='org-org' AND project_id='dev-project'
              AND execution_id=p_execution AND content_hash=p_manifest_hash;
            IF NOT FOUND OR encode(sha256(p.body),'hex') IS DISTINCT FROM p_manifest_hash
              OR convert_from(p.body,'UTF8')::jsonb->>'schemaVersion'
                IS DISTINCT FROM 'aos.model-eval-target-judge-shared-risk-manifest/v3' THEN
              RAISE EXCEPTION 'SHARED_EXECUTOR_MANIFEST_REQUIRED' USING ERRCODE='23514'; END IF;
            expected:=jsonb_array_length(convert_from(p.body,'UTF8')::jsonb->'cases')*2;
            SELECT count(*),count(DISTINCT (x.case_id,x.purpose)) INTO actual,unique_count
              FROM {s}.executor_certificate x WHERE org_id='org-org' AND project_id='dev-project'
                AND execution_id=p_execution;
            IF expected<2 OR actual<>expected OR unique_count<>expected THEN
              RAISE EXCEPTION 'SHARED_EXECUTOR_COMPLETE_SET_REQUIRED' USING ERRCODE='23514'; END IF;
            FOR r IN SELECT DISTINCT issuer_id,key_id FROM {s}.executor_certificate
              WHERE org_id='org-org' AND project_id='dev-project' AND execution_id=p_execution ORDER BY issuer_id,key_id LOOP
              SELECT e.epoch,e.root_hash,x.content_hash INTO h FROM {s}.issuer_epoch e
                JOIN {s}.issuer_root x USING(org_id,project_id,issuer_id,key_id)
                WHERE e.org_id='org-org' AND e.project_id='dev-project'
                  AND e.issuer_id=r.issuer_id AND e.key_id=r.key_id FOR SHARE OF e;
              IF NOT FOUND OR h.root_hash IS NULL OR h.root_hash IS DISTINCT FROM h.content_hash THEN
                RAISE EXCEPTION 'SHARED_EXECUTOR_ROOT_CURRENT_REQUIRED' USING ERRCODE='23514'; END IF;
            END LOOP;
            FOR r IN SELECT content_hash FROM {s}.executor_certificate WHERE org_id='org-org'
              AND project_id='dev-project' AND execution_id=p_execution ORDER BY content_hash LOOP
              SELECT epoch,active_hash INTO h FROM {s}.certificate_epoch WHERE org_id='org-org'
                AND project_id='dev-project' AND certificate_hash=r.content_hash FOR SHARE;
              IF NOT FOUND OR h.active_hash IS DISTINCT FROM r.content_hash THEN
                RAISE EXCEPTION 'SHARED_EXECUTOR_CERTIFICATE_CURRENT_REQUIRED' USING ERRCODE='23514'; END IF;
            END LOOP;
            FOR r IN SELECT x.*,b.identity_id,b.purpose AS binding_purpose,b.key_hash,
                b.description_hash,b.original_risk_hash,b.caller_xid,b.caller_pid
              FROM {s}.executor_certificate x LEFT JOIN {s}.shared_parent_certificate_identity_binding b
                ON (x.org_id,x.project_id,x.content_hash)=(b.org_id,b.project_id,b.certificate_hash)
              WHERE x.org_id='org-org' AND x.project_id='dev-project' AND x.execution_id=p_execution
              ORDER BY b.identity_id,x.content_hash LOOP
              IF r.description_hash IS DISTINCT FROM p_description_hash OR r.original_risk_hash IS DISTINCT FROM p_risk_hash
                OR r.caller_xid IS DISTINCT FROM pg_current_xact_id()::text
                OR r.caller_pid IS DISTINCT FROM pg_backend_pid() OR r.attempt<>1
                OR r.binding_purpose IS DISTINCT FROM r.purpose
                OR convert_from(r.body,'UTF8')::jsonb->>'schemaVersion'
                  IS DISTINCT FROM 'aos.model-eval-shared-parent-signed-certificate-envelope/v3'
                OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(convert_from(p.body,'UTF8')::jsonb->'cases') v
                  WHERE v->>'caseId'=r.case_id AND v->r.purpose->>'identityId'=r.identity_id
                    AND v->r.purpose->>'identityKeyHash'=r.key_hash) THEN
                RAISE EXCEPTION 'SHARED_EXECUTOR_ORIGINAL_ORIGIN_REQUIRED' USING ERRCODE='23514'; END IF;
              SELECT epoch,active,purpose,key_hash INTO h FROM {s}.identity_epoch
                WHERE org_id='org-org' AND project_id='dev-project' AND identity_id=r.identity_id FOR SHARE;
              IF NOT FOUND OR NOT h.active OR h.purpose IS DISTINCT FROM r.purpose OR h.key_hash IS DISTINCT FROM r.key_hash THEN
                RAISE EXCEPTION 'SHARED_EXECUTOR_IDENTITY_CURRENT_REQUIRED' USING ERRCODE='23514'; END IF;
            END LOOP;
            SELECT jsonb_agg(jsonb_build_object(
              'certificateHash',x.content_hash,'certificateBody',replace(encode(x.body,'base64'),E'\\n',''),
              'caseId',x.case_id,'purpose',x.purpose,'attempt',x.attempt,'issuerId',x.issuer_id,'issuerKeyId',x.key_id,
              'rootHash',root.content_hash,'rootBody',replace(encode(root.body,'base64'),E'\\n',''),
              'rootEpoch',re.epoch,'certificateEpoch',ce.epoch,'identityEpoch',i.epoch,
              'identityId',i.identity_id,'identityPurpose',i.purpose,'identityKeyHash',i.key_hash,'identityActive',i.active)
              ORDER BY x.content_hash) INTO packed FROM {s}.executor_certificate x
              JOIN {s}.issuer_root root USING(org_id,project_id,issuer_id,key_id)
              JOIN {s}.issuer_epoch re USING(org_id,project_id,issuer_id,key_id)
              JOIN {s}.certificate_epoch ce ON (x.org_id,x.project_id,x.content_hash)=(ce.org_id,ce.project_id,ce.certificate_hash)
              JOIN {s}.shared_parent_certificate_identity_binding b
                ON (x.org_id,x.project_id,x.content_hash)=(b.org_id,b.project_id,b.certificate_hash)
              JOIN {s}.identity_epoch i ON (b.org_id,b.project_id,b.identity_id,b.purpose,b.key_hash)
                =(i.org_id,i.project_id,i.identity_id,i.purpose,i.key_hash)
              WHERE x.org_id='org-org' AND x.project_id='dev-project' AND x.execution_id=p_execution;
            IF jsonb_array_length(packed) IS DISTINCT FROM expected THEN
              RAISE EXCEPTION 'SHARED_EXECUTOR_FINAL_SET_REQUIRED' USING ERRCODE='23514'; END IF;
            RETURN jsonb_build_object('manifestHash',p.content_hash,'manifestBody',replace(encode(p.body,'base64'),E'\\n',''),
              'certificates',packed,'callerXid',pg_current_xact_id()::text,'callerPid',pg_backend_pid(),
              'checkedAt',clock_timestamp(),'executionAllowed',false);
          END $shared$''',
        f'ALTER FUNCTION {FUNCTION} OWNER TO {ISSUER_OWNER}',
        f'REVOKE ALL ON FUNCTION {FUNCTION} FROM PUBLIC',
        f'GRANT EXECUTE ON FUNCTION {FUNCTION} TO aos_runtime',
    )


def _original(item, prefix, model):
    raw = base64.b64decode(item[prefix+'Body'], validate=True)
    digest = item[prefix+'Hash']
    if type(digest) is not str or re.fullmatch('[0-9a-f]{64}', digest) is None:
        raise ValueError('exact original metadata hash required')
    parsed = model.model_validate_json(raw)
    if hashlib.sha256(raw).hexdigest() != digest or canonical_hash(parsed.model_dump(mode='json', by_alias=True)) != digest:
        raise ValueError('canonical original metadata bytes required')
    return parsed


def read_shared_parent_executor_set(conn, scope, source_command, manifest, *,
        expected_content_hash, release_policy, artifact_bytes):
    """Same connection full preparation checks; metadata observation is not trust."""
    try:
        args = dict(expected_content_hash=expected_content_hash, release_policy=release_policy, artifact_bytes=artifact_bytes)
        description = read_shared_parent_description_origin(conn, scope, source_command, manifest, **args)
        plan = description.immutable.manifest
        def facts():
            with conn.cursor(row_factory=dict_row) as cur:
                return cur.execute('SELECT public.read_model_shared_parent_executor_set_facts(%s,%s,%s,%s) AS fact',
                    (plan.execution_id, description.immutable.manifest_hash, description.content_hash,
                     description.immutable.original_risk_hash)).fetchone()['fact']
        first = facts()
        raw_manifest = base64.b64decode(first['manifestBody'], validate=True)
        if (hashlib.sha256(raw_manifest).hexdigest() != first['manifestHash']
                or first['manifestHash'] != description.immutable.manifest_hash
                or type(plan).model_validate_json(raw_manifest) != plan
                or canonical_hash(plan.model_dump(mode='json',by_alias=True)) != first['manifestHash']):
            raise ValueError('exact original v3 manifest bytes required')
        expected = {(case.case_id, purpose) for case in plan.cases for purpose in ('target', 'judge')}
        observed = set()
        parsed_certificates = []
        for item in first['certificates']:
            cert = _original(item, 'certificate', ModelSharedParentRiskSignedCertificateEnvelope)
            root = _original(item, 'root', ModelEvalIssuerVerificationInput)
            signed = cert.certificate
            key = (signed.case_id, signed.purpose)
            if key not in expected or key in observed or (item['caseId'], item['purpose'], item['attempt'],
                item['issuerId'], item['issuerKeyId'], item['identityId'], item['identityPurpose'], item['identityKeyHash']) != (
                signed.case_id, signed.purpose, 1, signed.issuer_id, signed.issuer_key_id,
                signed.leg.identity_id, signed.purpose, signed.leg.identity_key_hash):
                raise ValueError('exact original certificate columns and full leg set required')
            if item['identityActive'] is not True or any(type(item[k]) is not int or item[k]<1
                    for k in ('rootEpoch','certificateEpoch','identityEpoch')):
                raise ValueError('current original metadata heads required')
            now = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
            validate_shared_parent_certificate_signature(description,cert,issuer_input=root,
                checked_at=now,revoked_identity_ids=frozenset())
            parsed_certificates.append((cert,root))
            observed.add(key)
        if observed != expected or first['executionAllowed'] is not False:
            raise ValueError('complete closed executor set required')
        again = read_shared_parent_description_origin(conn,scope,source_command,manifest,**args)
        final = facts()
        if again != description or any(first[k]!=final[k] for k in
                ('manifestHash','manifestBody','certificates','callerXid','callerPid','executionAllowed')):
            raise ValueError('original metadata changed after physical waits')
        if (final['callerXid'],final['callerPid']) != (description.immutable.caller_xid,description.immutable.caller_pid):
            raise ValueError('original physical caller changed')
        final_now = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        for cert,root in parsed_certificates:
            validate_shared_parent_certificate_signature(description,cert,issuer_input=root,
                checked_at=final_now,revoked_identity_ids=frozenset())
        return dict(description=description,metadata=final,root_provenance_verified=False,execution_allowed=False)
    except (KeyError,TypeError,ValueError,RuntimeError,psycopg.Error):
        raise ModelEvalOwnerRejected('SHARED_EXECUTOR_NATIVE_ORIGINAL_SET_REQUIRED') from None

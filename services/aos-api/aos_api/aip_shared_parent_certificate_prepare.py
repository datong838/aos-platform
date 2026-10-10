"""Signed metadata staging in the original risk transaction, never execution."""
import json

import psycopg
from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb

from aos_api.aip_model_eval_execution_authority import OWNER, ISSUER_OWNER, SCHEMA, ISSUER_SCHEMA
from aos_api.aip_model_eval_execution_contracts import ModelSharedParentRiskSignedCertificateEnvelope
from aos_api.aip_model_eval_execution_owner import ModelEvalOwnerRejected
from aos_api.aip_provider_capacity_source_consumer import _consumption_packet
from aos_api.aip_shared_parent_description_origin_reader import read_shared_parent_description_origin, FUNCTION as ORIGIN
from aos_api.aip_shared_parent_executor_set_reader import read_shared_parent_executor_set, FUNCTION as READER

from aos_api.aip_provider_capacity_publication_transaction import OWNER as SOURCE_OWNER

VERIFY = 'public.verify_model_shared_parent_certificate_signature(bytea,bytea,bytea)'
MANIFEST = 'public.prepare_model_shared_parent_manifest_origin(bytea,jsonb,uuid,text)'
FUNCTION = 'public.prepare_model_shared_parent_certificate_set(bytea,jsonb,uuid,text,bytea)'


def shared_parent_certificate_claim_sql():
    """Original complete set, pinned Root locks and v3 claim/signature checks.

    Fixed SQL fragment only. The caller must supply original validated doc,
    plan/hash/caller context and native verifier before any certificate writes.
    This does not establish Root provenance or grant admission permission.
    """
    s = ISSUER_SCHEMA
    return f'''            plan:=doc#>'{{immutable,manifest}}';expected:=jsonb_array_length(plan->'cases')*2;
            SELECT count(*),count(DISTINCT (v#>>'{{certificate,caseId}}',v#>>'{{certificate,purpose}}'))
              INTO actual,distinct_legs FROM jsonb_array_elements(items) v;
            IF actual<>expected OR distinct_legs<>expected THEN
              RAISE EXCEPTION 'SHARED_CERTIFICATE_COMPLETE_SET_REQUIRED' USING ERRCODE='23514'; END IF;
            -- All original root locks precede certificate/identity writes.
            FOR candidate IN SELECT jsonb_build_object('issuer',original.issuer,'key',original.key) FROM
              (SELECT DISTINCT v#>>'{{certificate,issuerId}}' AS issuer,v#>>'{{certificate,issuerKeyId}}' AS key
                FROM jsonb_array_elements(items) v ORDER BY issuer,key) original LOOP
              SELECT e.epoch,e.root_hash,r.content_hash INTO head FROM {s}.issuer_epoch e
                JOIN {s}.issuer_root r USING(org_id,project_id,issuer_id,key_id)
                WHERE e.org_id='org-org' AND e.project_id='dev-project'
                  AND e.issuer_id=candidate->>'issuer' AND e.key_id=candidate->>'key' FOR SHARE OF e;
              IF NOT FOUND OR head.root_hash IS NULL OR head.root_hash IS DISTINCT FROM head.content_hash THEN
                RAISE EXCEPTION 'SHARED_CERTIFICATE_PREPUBLISHED_ROOT_REQUIRED' USING ERRCODE='23514'; END IF;
            END LOOP;
            -- Validate every signature and complete original claim before any certificate insert.
            FOR envelope IN SELECT v FROM jsonb_array_elements(items) v LOOP
              claim:=envelope->'certificate';
              IF jsonb_typeof(envelope) IS DISTINCT FROM 'object'
                OR envelope-'schemaVersion'-'certificate'-'signatureBase64'<>'{{}}'::jsonb
                OR envelope->>'schemaVersion' IS DISTINCT FROM 'aos.model-eval-shared-parent-signed-certificate-envelope/v3'
                OR jsonb_typeof(claim) IS DISTINCT FROM 'object'
                OR claim-ARRAY['schemaVersion','tenant','executionId','manifestHash','requestHash','caseId','purpose','candidateRef',
                    'leg','issuerId','issuerKeyId','publicKeyBase64','validFrom','validUntil','descriptionHash','originalRiskHash','callerXid','callerPid']<>'{{}}'::jsonb
                OR claim->>'schemaVersion' IS DISTINCT FROM 'aos.model-eval-shared-parent-certificate-signing-input/v3'
                OR claim->'tenant' IS DISTINCT FROM plan->'tenant' OR claim->>'executionId' IS DISTINCT FROM p_plan::text
                OR claim->>'manifestHash' IS DISTINCT FROM doc#>>'{{immutable,manifestHash}}'
                OR claim->>'descriptionHash' IS DISTINCT FROM p_hash
                OR claim->>'originalRiskHash' IS DISTINCT FROM doc#>>'{{immutable,originalRiskHash}}'
                OR claim->>'callerXid' IS DISTINCT FROM pg_current_xact_id()::text
                OR claim->>'callerPid' IS DISTINCT FROM pg_backend_pid()::text
                OR claim->>'purpose' NOT IN ('target','judge') THEN
                RAISE EXCEPTION 'SHARED_CERTIFICATE_ORIGINAL_CLAIM_REQUIRED' USING ERRCODE='23514'; END IF;
              SELECT v->(claim->>'purpose') INTO leg FROM jsonb_array_elements(plan->'cases') v
                WHERE v->>'caseId'=claim->>'caseId';
              app:=plan->'judgeRequest'->(CASE WHEN claim->>'purpose'='target' THEN 'targetApplication' ELSE 'judgeGovernanceApplication' END);
              IF leg IS NULL OR claim->'leg' IS DISTINCT FROM leg OR claim->'candidateRef' IS DISTINCT FROM app->'request'->'targetRef'
                OR claim->>'requestHash' IS DISTINCT FROM (CASE WHEN claim->>'purpose'='target' THEN app->>'requestHash' ELSE plan->>'judgeRequestHash' END)
                OR octet_length(decode(claim->>'publicKeyBase64','base64')) IS DISTINCT FROM 32
                OR replace(encode(decode(claim->>'publicKeyBase64','base64'),'base64'),E'\\n','') IS DISTINCT FROM claim->>'publicKeyBase64'
                OR leg->>'identityKeyHash' IS DISTINCT FROM encode(sha256(decode(claim->>'publicKeyBase64','base64')),'hex') THEN
                RAISE EXCEPTION 'SHARED_CERTIFICATE_COMPLETE_LEG_REQUIRED' USING ERRCODE='23514'; END IF;
              SELECT r.*,convert_from(r.body,'UTF8')::jsonb AS original INTO root FROM {s}.issuer_root r
                WHERE org_id='org-org' AND project_id='dev-project' AND issuer_id=claim->>'issuerId' AND key_id=claim->>'issuerKeyId';
              start_at:=(claim->>'validFrom')::timestamptz;end_at:=(claim->>'validUntil')::timestamptz;
              IF NOT FOUND OR encode(sha256(root.body),'hex') IS DISTINCT FROM root.content_hash
                OR convert_to(public.canonical_asset_registry_jsonb(root.original),'UTF8') IS DISTINCT FROM root.body
                OR root.original->>'schemaVersion' IS DISTINCT FROM 'aos.model-eval-issuer-verification-input/v1'
                OR root.original->>'purpose' IS DISTINCT FROM 'model-eval-execution'
                OR root.original->'tenant' IS DISTINCT FROM plan->'tenant'
                OR root.original->>'issuerId' IS DISTINCT FROM claim->>'issuerId'
                OR root.original->>'issuerKeyId' IS DISTINCT FROM claim->>'issuerKeyId'
                OR octet_length(decode(root.original->>'publicKeyBase64','base64')) IS DISTINCT FROM 32
                OR (start_at<end_at AND start_at<=clock_timestamp() AND clock_timestamp()<end_at
                  AND (root.original->>'validFrom')::timestamptz<=start_at
                  AND end_at<=(root.original->>'validUntil')::timestamptz
                  AND end_at<=(plan#>>'{{judgeRequest,expiresAt}}')::timestamptz
                  AND (root.original->>'revokedAt' IS NULL OR clock_timestamp()<(root.original->>'revokedAt')::timestamptz)) IS DISTINCT FROM true
                OR octet_length(decode(envelope->>'signatureBase64','base64')) IS DISTINCT FROM 64
                OR replace(encode(decode(envelope->>'signatureBase64','base64'),'base64'),E'\\n','') IS DISTINCT FROM envelope->>'signatureBase64'
                OR public.verify_model_shared_parent_certificate_signature(decode(envelope->>'signatureBase64','base64'),
                  convert_to('AOS-MODEL-EVAL-SHARED-PARENT-CERTIFICATE-SIGNING-INPUT-v3'||chr(10)||public.canonical_asset_registry_jsonb(claim),'UTF8'),
                  decode(root.original->>'publicKeyBase64','base64')) IS DISTINCT FROM true THEN
                RAISE EXCEPTION 'SHARED_CERTIFICATE_SIGNATURE_OR_TIME_REQUIRED' USING ERRCODE='23514'; END IF;
            END LOOP;
'''


def shared_parent_native_verifier_requirement_sql():
    """Original exact C verifier/catalog requirement; no installation/grants."""
    return '''            IF NOT EXISTS(SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
              JOIN pg_language l ON l.oid=p.prolang JOIN pg_roles r ON r.oid=p.proowner
              WHERE n.nspname='aos_ed25519' AND p.proname='verify' AND p.proargtypes='17 17 17'::oidvector
                AND p.prorettype='boolean'::regtype AND p.probin='$libdir/aos_ed25519'
                AND p.prosrc='aos_ed25519_verify' AND l.lanname='c' AND NOT p.prosecdef
                AND p.provolatile='i' AND p.proisstrict AND r.rolname='aos_ed25519_owner' AND n.nspowner=r.oid
                AND NOT (r.rolcanlogin OR r.rolinherit OR r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls)
                AND NOT EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid=r.oid OR member=r.oid)) THEN
              RAISE EXCEPTION 'SHARED_CERTIFICATE_NATIVE_VERIFIER_REQUIRED' USING ERRCODE='42501'; END IF;
'''


def shared_parent_certificate_prepare_statements():
    """Explicit isolated protocol; prepublished root and pinned C verification."""
    s = ISSUER_SCHEMA
    return (
        f'GRANT EXECUTE ON FUNCTION {ORIGIN} TO {OWNER}',
        f'''CREATE FUNCTION {MANIFEST.split('(')[0]}(p_raw bytea,p_source jsonb,p_plan uuid,p_hash text)
          RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $manifest$
          DECLARE doc jsonb; raw bytea; previous record; BEGIN
            IF session_user<>'aos_provider_capacity_occupation'
              OR current_setting('role',true) IS DISTINCT FROM 'aos_runtime' THEN
              RAISE EXCEPTION 'SHARED_MANIFEST_NATIVE_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
            doc:=public.read_capacity_shared_risk_description_origin(p_raw,p_source,p_plan,p_hash);
            raw:=convert_to(public.canonical_asset_registry_jsonb(doc->'immutable'->'manifest'),'UTF8');
            IF doc->'executionAllowed' IS DISTINCT FROM 'false'::jsonb
              OR doc#>>'{{immutable,manifest,schemaVersion}}' IS DISTINCT FROM 'aos.model-eval-target-judge-shared-risk-manifest/v3'
              OR doc#>>'{{immutable,manifestHash}}' IS DISTINCT FROM encode(sha256(raw),'hex') THEN
              RAISE EXCEPTION 'SHARED_MANIFEST_ORIGINAL_REQUIRED' USING ERRCODE='23514'; END IF;
            INSERT INTO {SCHEMA}.manifest(org_id,project_id,execution_id,content_hash,body)
              VALUES('org-org','dev-project',p_plan::text,encode(sha256(raw),'hex'),raw) ON CONFLICT DO NOTHING;
            SELECT * INTO previous FROM {SCHEMA}.manifest WHERE org_id='org-org' AND project_id='dev-project'
              AND execution_id=p_plan::text;
            IF NOT FOUND OR previous.body IS DISTINCT FROM raw OR previous.content_hash IS DISTINCT FROM encode(sha256(raw),'hex') THEN
              RAISE EXCEPTION 'SHARED_MANIFEST_REPLAY_CONFLICT' USING ERRCODE='23514'; END IF;
            RETURN doc;
          END $manifest$''',
        f'ALTER FUNCTION {MANIFEST} OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {MANIFEST} FROM PUBLIC,aos_runtime,aos_provider_capacity_issuer',
        f'GRANT EXECUTE ON FUNCTION {MANIFEST} TO {ISSUER_OWNER}',
        f'''CREATE FUNCTION {VERIFY.split('(')[0]}(p_signature bytea,p_message bytea,p_public_key bytea)
          RETURNS boolean LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $verify$
          BEGIN
            IF session_user<>'aos_provider_capacity_occupation'
              OR current_setting('role',true) IS DISTINCT FROM 'aos_runtime'
              OR current_setting('transaction_isolation') IS DISTINCT FROM 'serializable'
              OR current_setting('transaction_read_only') IS DISTINCT FROM 'off'
              OR current_setting('TimeZone') IS DISTINCT FROM 'UTC'
              OR current_setting('session_replication_role') IS DISTINCT FROM 'origin'
              OR current_setting('aos.org_id',true) IS DISTINCT FROM 'org-org'
              OR current_setting('aos.project_id',true) IS DISTINCT FROM 'dev-project'
              OR octet_length(p_signature) IS DISTINCT FROM 64
              OR octet_length(p_public_key) IS DISTINCT FROM 32
              OR p_message IS NULL OR octet_length(p_message) NOT BETWEEN 59 AND 1048576
              OR substring(p_message FROM 1 FOR octet_length(convert_to('AOS-MODEL-EVAL-SHARED-PARENT-CERTIFICATE-SIGNING-INPUT-v3'||chr(10),'UTF8')))
                IS DISTINCT FROM convert_to('AOS-MODEL-EVAL-SHARED-PARENT-CERTIFICATE-SIGNING-INPUT-v3'||chr(10),'UTF8') THEN
              RAISE EXCEPTION 'SHARED_CERTIFICATE_VERIFIER_SCOPE_REQUIRED' USING ERRCODE='42501'; END IF;
            PERFORM aos_capacity_publication_private.require_current_source_installation();
            RETURN aos_ed25519.verify(p_signature,p_message,p_public_key);
          END $verify$''',
        f'ALTER FUNCTION {VERIFY} OWNER TO {SOURCE_OWNER}',
        f'REVOKE ALL ON FUNCTION {VERIFY} FROM PUBLIC,aos_runtime,aos_provider_capacity_issuer',
        f'GRANT EXECUTE ON FUNCTION {VERIFY} TO {ISSUER_OWNER}',
        f'''CREATE FUNCTION {FUNCTION.split('(')[0]}(
          p_raw bytea,p_source jsonb,p_plan uuid,p_hash text,p_certificates bytea)
          RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $prepare$
          DECLARE doc jsonb; plan jsonb; items jsonb; envelope jsonb; claim jsonb; leg jsonb; app jsonb;
            root record; head record; certificate_raw bytea; digest text; candidate jsonb; final_fact jsonb;
            expected integer; actual integer; distinct_legs integer; start_at timestamptz; end_at timestamptz;
          BEGIN
            IF session_user<>'aos_provider_capacity_occupation'
              OR current_setting('role',true) IS DISTINCT FROM 'aos_runtime'
              OR current_setting('transaction_isolation') IS DISTINCT FROM 'serializable'
              OR current_setting('transaction_read_only') IS DISTINCT FROM 'off'
              OR current_setting('TimeZone') IS DISTINCT FROM 'UTC'
              OR current_setting('session_replication_role') IS DISTINCT FROM 'origin'
              OR current_setting('aos.org_id',true) IS DISTINCT FROM 'org-org'
              OR current_setting('aos.project_id',true) IS DISTINCT FROM 'dev-project'
              OR p_certificates IS NULL OR octet_length(p_certificates) NOT BETWEEN 2 AND 1048576 THEN
              RAISE EXCEPTION 'SHARED_CERTIFICATE_NATIVE_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
{shared_parent_native_verifier_requirement_sql()}            items:=convert_from(p_certificates,'UTF8')::jsonb;
            IF jsonb_typeof(items) IS DISTINCT FROM 'array'
              OR convert_to(public.canonical_asset_registry_jsonb(items),'UTF8') IS DISTINCT FROM p_certificates THEN
              RAISE EXCEPTION 'SHARED_CERTIFICATE_CANONICAL_SET_REQUIRED' USING ERRCODE='23514'; END IF;
            doc:=public.prepare_model_shared_parent_manifest_origin(p_raw,p_source,p_plan,p_hash);
{shared_parent_certificate_claim_sql()}            FOR envelope IN SELECT v FROM jsonb_array_elements(items) v ORDER BY encode(sha256(convert_to(public.canonical_asset_registry_jsonb(v),'UTF8')),'hex') LOOP
              claim:=envelope->'certificate';certificate_raw:=convert_to(public.canonical_asset_registry_jsonb(envelope),'UTF8');digest:=encode(sha256(certificate_raw),'hex');
              INSERT INTO {s}.executor_certificate(org_id,project_id,execution_id,case_id,purpose,attempt,issuer_id,key_id,content_hash,body)
                VALUES('org-org','dev-project',p_plan::text,claim->>'caseId',claim->>'purpose',1,claim->>'issuerId',claim->>'issuerKeyId',digest,certificate_raw)
                ON CONFLICT DO NOTHING;
              IF NOT EXISTS(SELECT 1 FROM {s}.executor_certificate WHERE org_id='org-org' AND project_id='dev-project'
                AND execution_id=p_plan::text AND case_id=claim->>'caseId' AND purpose=claim->>'purpose' AND attempt=1
                AND content_hash=digest AND executor_certificate.body=certificate_raw) THEN
                RAISE EXCEPTION 'SHARED_CERTIFICATE_REPLAY_CONFLICT' USING ERRCODE='23514'; END IF;
            END LOOP;
            FOR digest IN SELECT encode(sha256(convert_to(public.canonical_asset_registry_jsonb(v),'UTF8')),'hex')
              FROM jsonb_array_elements(items) v ORDER BY 1 LOOP
              PERFORM 1 FROM {s}.certificate_epoch WHERE org_id='org-org' AND project_id='dev-project'
                AND certificate_hash=digest AND active_hash=digest FOR SHARE;
              IF NOT FOUND THEN RAISE EXCEPTION 'SHARED_CERTIFICATE_CURRENT_HEAD_REQUIRED' USING ERRCODE='23514'; END IF;
            END LOOP;
            FOR envelope IN SELECT v FROM jsonb_array_elements(items) v ORDER BY v#>>'{{certificate,leg,identityId}}',v#>>'{{certificate,caseId}}' LOOP
              digest:=encode(sha256(convert_to(public.canonical_asset_registry_jsonb(envelope),'UTF8')),'hex');
              IF NOT EXISTS(SELECT 1 FROM {s}.shared_parent_certificate_identity_binding
                WHERE org_id='org-org' AND project_id='dev-project' AND certificate_hash=digest) THEN
                INSERT INTO {s}.shared_parent_certificate_identity_binding(org_id,project_id,certificate_hash)
                  VALUES('org-org','dev-project',digest);
              END IF;
            END LOOP;
            final_fact:=public.read_model_shared_parent_executor_set_facts(p_plan::text,doc#>>'{{immutable,manifestHash}}',p_hash,doc#>>'{{immutable,originalRiskHash}}');
            IF public.prepare_model_shared_parent_manifest_origin(p_raw,p_source,p_plan,p_hash) IS DISTINCT FROM doc THEN
              RAISE EXCEPTION 'SHARED_CERTIFICATE_FINAL_ORIGINAL_REQUIRED' USING ERRCODE='23514'; END IF;
            FOR envelope IN SELECT v FROM jsonb_array_elements(items) v LOOP
              SELECT convert_from(body,'UTF8')::jsonb AS original INTO root FROM {s}.issuer_root
                WHERE org_id='org-org' AND project_id='dev-project' AND issuer_id=envelope#>>'{{certificate,issuerId}}'
                  AND key_id=envelope#>>'{{certificate,issuerKeyId}}';
              IF ((envelope#>>'{{certificate,validFrom}}')::timestamptz<=clock_timestamp()
                AND clock_timestamp()<(envelope#>>'{{certificate,validUntil}}')::timestamptz
                AND (root.original->>'validFrom')::timestamptz<=clock_timestamp()
                AND clock_timestamp()<(root.original->>'validUntil')::timestamptz
                AND (root.original->>'revokedAt' IS NULL OR clock_timestamp()<(root.original->>'revokedAt')::timestamptz)) IS DISTINCT FROM true THEN
                RAISE EXCEPTION 'SHARED_CERTIFICATE_FINAL_EXPIRY' USING ERRCODE='23514'; END IF;
            END LOOP;
            RETURN jsonb_build_object('metadata',final_fact,'executionAllowed',false,'rootProvenanceVerified',false);
          END $prepare$''',
        f'ALTER FUNCTION {FUNCTION} OWNER TO {ISSUER_OWNER}',
        f'REVOKE ALL ON FUNCTION {FUNCTION} FROM PUBLIC,aos_provider_capacity_issuer',
        f'GRANT EXECUTE ON FUNCTION {FUNCTION} TO aos_runtime',
    )


def prepare_shared_parent_certificate_set(conn, scope, source_command, manifest, certificates, *,
        expected_content_hash, release_policy, artifact_bytes):
    """A savepoint makes post-write Python failures atomic within caller scope."""
    try:
        if type(conn) is not psycopg.Connection or conn.info.transaction_status != TransactionStatus.INTRANS:
            raise ValueError('original native caller transaction required')
        parsed = [ModelSharedParentRiskSignedCertificateEnvelope.model_validate(item) for item in certificates]
        raw = json.dumps([item.model_dump(mode='json',by_alias=True) for item in parsed],
            ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        args = dict(expected_content_hash=expected_content_hash,release_policy=release_policy,artifact_bytes=artifact_bytes)
        with conn.transaction():
            description = read_shared_parent_description_origin(conn,scope,source_command,manifest,**args)
            packet = _consumption_packet(source_command)
            staged = conn.execute('SELECT public.prepare_model_shared_parent_certificate_set(%s,%s::jsonb,%s::uuid,%s,%s) AS fact',
                (packet,Jsonb(source_command.source_ref.model_dump(mode='json',by_alias=True)),description.plan_id,expected_content_hash,raw)).fetchone()['fact']
            if staged['executionAllowed'] is not False or staged['rootProvenanceVerified'] is not False:
                raise ValueError('preparation cannot grant trust or execution')
            return read_shared_parent_executor_set(conn,scope,source_command,manifest,**args)
    except Exception:
        raise ModelEvalOwnerRejected('SHARED_CERTIFICATE_NATIVE_PREPARATION_REQUIRED') from None

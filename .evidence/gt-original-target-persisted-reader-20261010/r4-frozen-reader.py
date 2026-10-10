"""Private v2 Target necessary evidence, never execution or root provenance.

Stored signatures, current metadata heads and a committed insertion origin do
not prove bootstrap authority, joint admission, real transport, Usage or fees.
The original caller owns its transaction and retains all shared locks.
"""
import base64
import hashlib
import json
import re

import psycopg
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row

from aos_api.aip_contracts import TenantContext
from aos_api.aip_model_eval_execution_contracts import (
    ModelEvalCasePersistenceBinding, ModelEvalIssuerVerificationInput,
    ModelEvalTargetJudgeExecutionManifest, ModelOriginalTargetSignedCaseEnvelope,
    ModelOriginalTargetSignedCertificateEnvelope, _plain_contract_input,
    validate_original_target_case_signature,
)
from aos_api.aip_model_eval_execution_authority import ISSUER_OWNER, ISSUER_SCHEMA, SCHEMA
from aos_api.aip_model_eval_execution_reader import read_model_certificate_epoch
from aos_api.aip_model_runtime_store import canonical_hash


def original_target_identity_statements():
    """Explicit isolated v2 metadata artifact, never migration or trust grant.

    Reuses original global identity_epoch/transition/withdrawal. The legacy v1
    binding and its trigger are untouched. Runtime receives no access.
    """
    s = ISSUER_SCHEMA
    table = s + '.original_target_certificate_identity_binding'
    return (
        f'''CREATE TABLE {table}(org_id text NOT NULL CHECK(org_id='org-org'),
            project_id text NOT NULL CHECK(project_id='dev-project'),
            certificate_hash text NOT NULL CHECK(certificate_hash ~ '^[0-9a-f]{{64}}$'),
            identity_id text NOT NULL CHECK(length(identity_id) BETWEEN 1 AND 200 AND identity_id=btrim(identity_id)),
            purpose text NOT NULL CHECK(purpose='target'),key_hash text NOT NULL,
            PRIMARY KEY(org_id,project_id,certificate_hash),
            FOREIGN KEY(org_id,project_id,certificate_hash) REFERENCES {s}.executor_certificate(org_id,project_id,content_hash),
            FOREIGN KEY(org_id,project_id,identity_id,purpose,key_hash) REFERENCES {s}.identity_epoch(org_id,project_id,identity_id,purpose,key_hash))''',
        f'ALTER TABLE {table} OWNER TO {ISSUER_OWNER}',
        f'REVOKE ALL ON {table} FROM PUBLIC,aos_runtime,aos_provider_capacity_issuer',
        f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY',
        f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY',
        f'''CREATE POLICY original_target_binding_scope ON {table} TO {ISSUER_OWNER}
            USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
            WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))''',
        f'''CREATE FUNCTION {s}.derive_original_target_identity() RETURNS trigger
            LANGUAGE plpgsql SET search_path=pg_catalog AS $v2$
            DECLARE c record; j jsonb; BEGIN
            SELECT h.root_hash INTO c FROM {s}.issuer_epoch h JOIN {s}.executor_certificate x
              ON (h.org_id,h.project_id,h.issuer_id,h.key_id)=(x.org_id,x.project_id,x.issuer_id,x.key_id)
              WHERE x.org_id=NEW.org_id AND x.project_id=NEW.project_id AND x.content_hash=NEW.certificate_hash FOR SHARE OF h;
            IF NOT FOUND OR c.root_hash IS NULL THEN RAISE EXCEPTION 'ORIGINAL_TARGET_ROOT_INACTIVE' USING ERRCODE='42501'; END IF;
            SELECT x.*,h.active_hash INTO c FROM {s}.executor_certificate x JOIN {s}.certificate_epoch h
              ON (h.org_id,h.project_id,h.certificate_hash)=(x.org_id,x.project_id,x.content_hash)
              WHERE x.org_id=NEW.org_id AND x.project_id=NEW.project_id AND x.content_hash=NEW.certificate_hash FOR SHARE OF h;
            IF NOT FOUND OR c.active_hash IS NULL THEN RAISE EXCEPTION 'ORIGINAL_TARGET_CERTIFICATE_INACTIVE' USING ERRCODE='42501'; END IF;
            j:=convert_from(c.body,'UTF8')::jsonb;
            IF j->>'schemaVersion' IS DISTINCT FROM 'aos.model-eval-original-target-signed-certificate-envelope/v2'
              OR j#>>'{{certificate,schemaVersion}}' IS DISTINCT FROM 'aos.model-eval-original-target-certificate-signing-input/v2'
              OR c.purpose IS DISTINCT FROM 'target' OR c.attempt<>1
              OR j#>>'{{certificate,tenant,orgId}}' IS DISTINCT FROM NEW.org_id
              OR j#>>'{{certificate,tenant,projectId}}' IS DISTINCT FROM NEW.project_id
              OR j#>>'{{certificate,executionId}}' IS DISTINCT FROM c.execution_id
              OR j#>>'{{certificate,caseId}}' IS DISTINCT FROM c.case_id
              OR j#>>'{{certificate,purpose}}' IS DISTINCT FROM c.purpose
              OR j#>>'{{certificate,issuerId}}' IS DISTINCT FROM c.issuer_id
              OR j#>>'{{certificate,issuerKeyId}}' IS DISTINCT FROM c.key_id
              OR octet_length(decode(j#>>'{{certificate,publicKeyBase64}}','base64')) IS DISTINCT FROM 32
              OR j#>>'{{certificate,leg,identityKeyHash}}' IS DISTINCT FROM encode(sha256(decode(j#>>'{{certificate,publicKeyBase64}}','base64')),'hex')
            THEN RAISE EXCEPTION 'ORIGINAL_TARGET_CERTIFICATE_BINDING' USING ERRCODE='42501'; END IF;
            NEW.identity_id:=j#>>'{{certificate,leg,identityId}}';NEW.purpose:=c.purpose;NEW.key_hash:=j#>>'{{certificate,leg,identityKeyHash}}';
            INSERT INTO {s}.identity_epoch(org_id,project_id,identity_id,purpose,key_hash,epoch,version,active)
              VALUES(NEW.org_id,NEW.project_id,NEW.identity_id,NEW.purpose,NEW.key_hash,1,1,true)
              ON CONFLICT(org_id,project_id,identity_id) DO UPDATE SET version=identity_epoch.version+1
              WHERE identity_epoch.active AND identity_epoch.purpose=EXCLUDED.purpose AND identity_epoch.key_hash=EXCLUDED.key_hash;
            IF NOT FOUND THEN RAISE EXCEPTION 'ORIGINAL_TARGET_IDENTITY_BOUND_OR_REVOKED' USING ERRCODE='42501'; END IF;
            RETURN NEW; END $v2$''',
        f'ALTER FUNCTION {s}.derive_original_target_identity() OWNER TO {ISSUER_OWNER}',
        f'REVOKE ALL ON FUNCTION {s}.derive_original_target_identity() FROM PUBLIC,aos_runtime,aos_provider_capacity_issuer',
        f'CREATE TRIGGER original_target_binding_insert BEFORE INSERT ON {table} FOR EACH ROW EXECUTE FUNCTION {s}.derive_original_target_identity()',
        f'CREATE TRIGGER original_target_binding_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION {s}.immutable_issuer_history()',
        f'CREATE TRIGGER original_target_binding_no_truncate BEFORE TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION {s}.immutable_issuer_history()',
    )


def _require(ok, reason):
    if not ok:
        raise ValueError(reason)


def _read_persisted_original_target_case(conn, *, expected_tenant,
        execution_id, manifest_hash, case_id, binding, expected_identity_epoch,
        input_bytes, output_bytes) -> None:
    """Read original v2 bytes and committed origin; grant no admission.

    Does not repair callers, create holds/Intents, install objects, write rows,
    commit, dispatch or validate a final joint receipt. Runtime is denied.
    """
    _require(type(conn) is psycopg.Connection
        and conn.info.transaction_status == TransactionStatus.INTRANS,
        'native original Target caller transaction required')
    _require(isinstance(expected_tenant, TenantContext), 'typed original Target tenant required')
    tenant = TenantContext.model_validate(_plain_contract_input(expected_tenant))
    _require((tenant.org_id, tenant.project_id) == ('org-org', 'dev-project'), 'positive original Target tenant required')
    _require(all(type(v) is str and 1 <= len(v) <= 200 and v == v.strip()
        for v in (execution_id, case_id)), 'exact original Target identifiers required')
    _require(type(manifest_hash) is str and re.fullmatch(r'[0-9a-f]{64}', manifest_hash) is not None,
        'exact original Target manifest hash required')
    _require(type(expected_identity_epoch) is int and expected_identity_epoch >= 1,
        'native original Target identity epoch required')
    _require(all(type(v) is bytes and len(v) <= 1048576 for v in (input_bytes, output_bytes)),
        'bounded native original Target wire/output bytes required')
    frozen = ModelEvalCasePersistenceBinding.model_validate(binding)

    def parse(row, expected_hash, model):
        _require(row is not None and isinstance(row['body'], (bytes, bytearray, memoryview)),
            'original persisted Target bytes required')
        raw = bytes(row['body'])
        _require(hashlib.sha256(raw).hexdigest() == row['content_hash'] == expected_hash,
            'original persisted Target hash drifted')
        value = model.model_validate_json(raw)
        _require(canonical_hash(value.model_dump(mode='json', by_alias=True)) == expected_hash,
            'canonical complete original Target bytes required')
        _require((row['org_id'], row['project_id']) == (tenant.org_id, tenant.project_id),
            'original Target row tenant drifted')
        return value

    try:
        with conn.cursor(row_factory=dict_row) as cur:
            context = cur.execute("""SELECT current_user AS role,
                current_setting('aos.org_id',true) AS org,
                current_setting('aos.project_id',true) AS project,
                current_setting('transaction_isolation') AS isolation,
                pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid""").fetchone()
            _require((context['role'],context['org'],context['project'],context['isolation']) ==
                (ISSUER_OWNER,tenant.org_id,tenant.project_id,'serializable'),
                'exact private original Target SERIAL caller required')
            plan_row = cur.execute(f'SELECT * FROM {SCHEMA}.manifest WHERE org_id=%s AND project_id=%s AND execution_id=%s',
                (tenant.org_id,tenant.project_id,execution_id)).fetchone()
            cert_row = cur.execute(f'SELECT * FROM {ISSUER_SCHEMA}.executor_certificate WHERE org_id=%s AND project_id=%s AND content_hash=%s',
                (tenant.org_id,tenant.project_id,frozen.certificate_hash)).fetchone()
            _require(cert_row is not None, 'original Target certificate required')
            root_row = cur.execute(f'SELECT * FROM {ISSUER_SCHEMA}.issuer_root WHERE org_id=%s AND project_id=%s AND issuer_id=%s AND key_id=%s',
                (tenant.org_id,tenant.project_id,cert_row['issuer_id'],cert_row['key_id'])).fetchone()
        plan = parse(plan_row,manifest_hash,ModelEvalTargetJudgeExecutionManifest)
        cert = parse(cert_row,frozen.certificate_hash,ModelOriginalTargetSignedCertificateEnvelope)
        root = parse(root_row,frozen.root_hash,ModelEvalIssuerVerificationInput)
        claim = cert.certificate
        _require(plan.tenant == tenant and plan.execution_id == execution_id
            and plan_row['execution_id'] == execution_id, 'original Target plan identity drifted')
        _require(claim.tenant == tenant and claim.execution_id == execution_id and claim.case_id == case_id
            and (cert_row['execution_id'],cert_row['case_id'],cert_row['purpose'],cert_row['attempt'],cert_row['issuer_id'],cert_row['key_id']) ==
            (execution_id,case_id,'target',1,claim.issuer_id,claim.issuer_key_id),
            'original Target certificate header drifted')
        _require(root.tenant == tenant and (root_row['issuer_id'],root_row['key_id']) ==
            (root.issuer_id,root.issuer_key_id), 'original Target root header drifted')
        # Original lock helpers retain root -> certificate -> identity order.
        read_model_certificate_epoch(conn,expected_tenant=tenant,issuer_id=claim.issuer_id,
            issuer_key_id=claim.issuer_key_id,expected_epoch=frozen.root_epoch,root_hash=frozen.root_hash,
            certificate_hash=frozen.certificate_hash,expected_certificate_epoch=frozen.certificate_epoch,
            execution_id=execution_id,case_id=case_id,purpose='target')
        with conn.cursor(row_factory=dict_row) as cur:
            identity = cur.execute(f'''SELECT h.epoch,h.active,h.key_hash FROM {ISSUER_SCHEMA}.identity_epoch h
                JOIN {ISSUER_SCHEMA}.original_target_certificate_identity_binding b
                  ON (h.org_id,h.project_id,h.identity_id,h.purpose,h.key_hash)=(b.org_id,b.project_id,b.identity_id,b.purpose,b.key_hash)
                WHERE b.org_id=%s AND b.project_id=%s AND b.certificate_hash=%s AND b.identity_id=%s AND b.purpose='target' FOR SHARE OF h''',
                (tenant.org_id,tenant.project_id,frozen.certificate_hash,claim.leg.identity_id)).fetchone()
            _require(identity is not None and identity['active'] and identity['epoch']==expected_identity_epoch
                and identity['key_hash']==claim.leg.identity_key_hash, 'original Target identity revoked or binding drifted')
            row = cur.execute(f'SELECT * FROM {SCHEMA}.case_result WHERE org_id=%s AND project_id=%s AND execution_id=%s AND case_id=%s AND purpose=%s AND attempt=1',
                (tenant.org_id,tenant.project_id,execution_id,case_id,'target')).fetchone()
            case = parse(row,frozen.case_hash,ModelOriginalTargetSignedCaseEnvelope)
            _require((row['execution_id'],row['case_id'],row['purpose'],row['attempt']) ==
                (execution_id,case_id,'target',1), 'original Target result header drifted')
            origin = cur.execute(f'''SELECT origin_xid::text AS xid,origin_pid AS pid,
                pg_xact_status(origin_xid) AS status FROM {ISSUER_SCHEMA}.target_result_origin
                WHERE org_id=%s AND project_id=%s AND execution_id=%s AND case_id=%s
                  AND purpose='target' AND attempt=1 AND content_hash=%s''',
                (tenant.org_id,tenant.project_id,execution_id,case_id,frozen.case_hash)).fetchone()
            _require(origin is not None and type(origin['xid']) is str
                and re.fullmatch(r'[1-9][0-9]*',origin['xid']) is not None
                and type(origin['pid']) is int and origin['pid'] > 0
                and origin['xid'] != context['xid'] and origin['status'] == 'committed',
                'native committed original Target insertion origin required')
            final = cur.execute('SELECT clock_timestamp() AS now,pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
        _require((final['xid'],final['pid']) == (context['xid'],context['pid']), 'original Target caller drifted')
        _require(root_row['created_at'] <= cert_row['created_at'] <= case.payload.claim.occurred_at <= final['now'],
            'original Target creation/occurrence order drifted')
        # Recheck all signed windows only after every original lock/read wait.
        validate_original_target_case_signature(plan,case,certificate_envelope=cert,
            issuer_input=root,checked_at=final['now'],revoked_identity_ids=frozenset(),
            input_bytes=input_bytes,output_bytes=output_bytes)
        return plan,case,cert,root,context
    except psycopg.Error as exc:
        raise ValueError('original Target persisted evidence unavailable') from exc


def validate_persisted_original_target_case(conn, *, expected_tenant,
        execution_id, manifest_hash, case_id, binding, expected_identity_epoch,
        input_bytes, output_bytes) -> None:
    """Validate necessary original v2 facts, preserving caller locks and no grant."""
    _read_persisted_original_target_case(conn,expected_tenant=expected_tenant,
        execution_id=execution_id,manifest_hash=manifest_hash,case_id=case_id,
        binding=binding,expected_identity_epoch=expected_identity_epoch,
        input_bytes=input_bytes,output_bytes=output_bytes)


def build_original_target_judge_input(conn, *, expected_output, **target_args) -> bytes:
    """Bind a Judge input to current stored original v2 Target facts.

    Private SERIAL caller only. Signatures and committed insertion provenance
    are necessary facts; this neither proves transport/Usage nor authorizes
    Judge dispatch, a runtime caller or a final joint commit.
    """
    plan,target,certificate,root,context = _read_persisted_original_target_case(conn,**target_args)
    case = next(item for item in plan.cases if item.case_id == target.payload.claim.case_id)
    if case.expected_hash is None:
        _require(expected_output is None,'absent original expected artifact requires no bytes')
    else:
        _require(type(expected_output) is bytes and len(expected_output) <= 1048576
            and hashlib.sha256(expected_output).hexdigest() == case.expected_hash,
            'exact bounded original expected hash witness required')
    payload = dict(schemaVersion='aos.model-eval-original-target-judge-input/v2',
        tenant=plan.tenant.model_dump(mode='json',by_alias=True),
        executionId=plan.execution_id,manifestHash=target.payload.claim.manifest_hash,
        judgeRequestHash=plan.judge_request_hash,caseId=case.case_id,
        judgeLeg=case.judge.model_dump(mode='json',by_alias=True),
        targetCaseHash=canonical_hash(target.model_dump(mode='json',by_alias=True)),
        targetCertificateHash=target.payload.certificate_hash,
        actualHash=target.payload.claim.output_hash,
        actualBase64=base64.b64encode(target_args['output_bytes']).decode('ascii'),
        expectedHash=case.expected_hash,
        expectedBase64=None if expected_output is None else base64.b64encode(expected_output).decode('ascii'),
        executionAllowed=False)
    raw = json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            final = cur.execute('SELECT clock_timestamp() AS now,pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
    except psycopg.Error as exc:
        raise ValueError('original Judge input final currentness unavailable') from exc
    _require((final['xid'],final['pid']) == (context['xid'],context['pid']),
        'original Judge input caller drifted')
    validate_original_target_case_signature(plan,target,certificate_envelope=certificate,
        issuer_input=root,checked_at=final['now'],revoked_identity_ids=frozenset(),
        input_bytes=target_args['input_bytes'],output_bytes=target_args['output_bytes'])
    return raw

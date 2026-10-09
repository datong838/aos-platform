"""Private v3 necessary identity metadata. No bootstrap or execution authority.

Explicit isolated installation only. Legacy domains, migration activation and
runtime ACLs are untouched. A signed description is not a native risk row.
"""
import hashlib
import re

import psycopg
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row

from aos_api.aip_contracts import TenantContext
from aos_api.aip_model_eval_execution_authority import ISSUER_OWNER, ISSUER_SCHEMA, SCHEMA
from aos_api.aip_model_eval_execution_contracts import (
    ModelEvalIssuerVerificationInput, ModelEvalTargetJudgeSharedRiskManifest,
    ModelSharedParentRiskSignedCertificateEnvelope, _plain_contract_input,
    validate_shared_parent_certificate_signature,
)
from aos_api.aip_model_eval_execution_reader import read_model_certificate_epoch
from aos_api.aip_model_runtime_store import canonical_hash
from aos_api.aip_physical_capacity_occupation_contracts import SharedParentRiskDescriptionPreparation

TABLE = ISSUER_SCHEMA + '.shared_parent_certificate_identity_binding'


def shared_parent_identity_statements():
    """Private metadata artifact; reuses original global identity withdrawals."""
    s = ISSUER_SCHEMA
    return (
        f'''CREATE TABLE {TABLE}(org_id text NOT NULL CHECK(org_id='org-org'),
            project_id text NOT NULL CHECK(project_id='dev-project'),
            certificate_hash text NOT NULL CHECK(certificate_hash ~ '^[0-9a-f]{{64}}$'),
            identity_id text NOT NULL CHECK(length(identity_id) BETWEEN 1 AND 200 AND identity_id=btrim(identity_id)),
            purpose text NOT NULL CHECK(purpose IN ('target','judge')),
            key_hash text NOT NULL CHECK(key_hash ~ '^[0-9a-f]{{64}}$'),
            description_hash text NOT NULL CHECK(description_hash ~ '^sha256:[0-9a-f]{{64}}$'),
            original_risk_hash text NOT NULL CHECK(original_risk_hash ~ '^sha256:[0-9a-f]{{64}}$'),
            caller_xid text NOT NULL CHECK(caller_xid ~ '^[1-9][0-9]*$'),
            caller_pid integer NOT NULL CHECK(caller_pid>0),
            PRIMARY KEY(org_id,project_id,certificate_hash),
            FOREIGN KEY(org_id,project_id,certificate_hash) REFERENCES {s}.executor_certificate(org_id,project_id,content_hash),
            FOREIGN KEY(org_id,project_id,identity_id,purpose,key_hash) REFERENCES {s}.identity_epoch(org_id,project_id,identity_id,purpose,key_hash))''',
        f'ALTER TABLE {TABLE} OWNER TO {ISSUER_OWNER}',
        f'REVOKE ALL ON {TABLE} FROM PUBLIC,aos_runtime,aos_provider_capacity_issuer',
        f'ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY',
        f'ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY',
        f'''CREATE POLICY shared_parent_identity_scope ON {TABLE} TO {ISSUER_OWNER}
            USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
            WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))''',
        f'''CREATE FUNCTION {s}.derive_shared_parent_identity() RETURNS trigger
            LANGUAGE plpgsql SET search_path=pg_catalog AS $v3$
            DECLARE c record; j jsonb; m jsonb; leg jsonb; BEGIN
            SELECT h.root_hash INTO c FROM {s}.issuer_epoch h JOIN {s}.executor_certificate x
                ON (h.org_id,h.project_id,h.issuer_id,h.key_id)=(x.org_id,x.project_id,x.issuer_id,x.key_id)
                WHERE x.org_id=NEW.org_id AND x.project_id=NEW.project_id AND x.content_hash=NEW.certificate_hash FOR SHARE OF h;
            IF NOT FOUND OR c.root_hash IS NULL THEN RAISE EXCEPTION 'SHARED_PARENT_ROOT_INACTIVE' USING ERRCODE='42501'; END IF;
            SELECT x.*,h.active_hash,p.body AS manifest_body,p.content_hash AS manifest_hash INTO c
                FROM {s}.executor_certificate x JOIN {s}.certificate_epoch h
                ON (h.org_id,h.project_id,h.certificate_hash)=(x.org_id,x.project_id,x.content_hash)
                JOIN {SCHEMA}.manifest p ON (p.org_id,p.project_id,p.execution_id)=(x.org_id,x.project_id,x.execution_id)
                WHERE x.org_id=NEW.org_id AND x.project_id=NEW.project_id AND x.content_hash=NEW.certificate_hash FOR SHARE OF h;
            IF NOT FOUND OR c.active_hash IS NULL THEN RAISE EXCEPTION 'SHARED_PARENT_CERTIFICATE_INACTIVE' USING ERRCODE='42501'; END IF;
            j:=convert_from(c.body,'UTF8')::jsonb;m:=convert_from(c.manifest_body,'UTF8')::jsonb;
            SELECT v->c.purpose INTO leg FROM jsonb_array_elements(m->'cases') v WHERE v->>'caseId'=c.case_id;
            IF j->>'schemaVersion' IS DISTINCT FROM 'aos.model-eval-shared-parent-signed-certificate-envelope/v3'
                OR j#>>'{{certificate,schemaVersion}}' IS DISTINCT FROM 'aos.model-eval-shared-parent-certificate-signing-input/v3'
                OR m->>'schemaVersion' IS DISTINCT FROM 'aos.model-eval-target-judge-shared-risk-manifest/v3'
                OR m->>'executionId' IS DISTINCT FROM c.execution_id
                OR m#>>'{{tenant,orgId}}' IS DISTINCT FROM NEW.org_id
                OR m#>>'{{tenant,projectId}}' IS DISTINCT FROM NEW.project_id
                OR c.attempt<>1 OR leg IS NULL OR j#>'{{certificate,leg}}' IS DISTINCT FROM leg
                OR j#>>'{{certificate,manifestHash}}' IS DISTINCT FROM c.manifest_hash
                OR j#>>'{{certificate,requestHash}}' IS DISTINCT FROM (CASE WHEN c.purpose='target' THEN m#>>'{{judgeRequest,targetApplication,requestHash}}' ELSE m->>'judgeRequestHash' END)
                OR j#>'{{certificate,candidateRef}}' IS DISTINCT FROM (CASE WHEN c.purpose='target' THEN m#>'{{judgeRequest,targetApplication,request,targetRef}}' ELSE m#>'{{judgeRequest,judgeGovernanceApplication,request,targetRef}}' END)
                OR j#>>'{{certificate,tenant,orgId}}' IS DISTINCT FROM NEW.org_id
                OR j#>>'{{certificate,tenant,projectId}}' IS DISTINCT FROM NEW.project_id
                OR j#>>'{{certificate,executionId}}' IS DISTINCT FROM c.execution_id
                OR j#>>'{{certificate,caseId}}' IS DISTINCT FROM c.case_id
                OR j#>>'{{certificate,purpose}}' IS DISTINCT FROM c.purpose
                OR j#>>'{{certificate,issuerId}}' IS DISTINCT FROM c.issuer_id
                OR j#>>'{{certificate,issuerKeyId}}' IS DISTINCT FROM c.key_id
                OR octet_length(decode(j#>>'{{certificate,publicKeyBase64}}','base64')) IS DISTINCT FROM 32
                OR leg->>'identityKeyHash' IS DISTINCT FROM encode(sha256(decode(j#>>'{{certificate,publicKeyBase64}}','base64')),'hex')
            THEN RAISE EXCEPTION 'SHARED_PARENT_CERTIFICATE_BINDING' USING ERRCODE='42501'; END IF;
            NEW.identity_id:=leg->>'identityId';NEW.purpose:=c.purpose;NEW.key_hash:=leg->>'identityKeyHash';
            NEW.description_hash:=j#>>'{{certificate,descriptionHash}}';NEW.original_risk_hash:=j#>>'{{certificate,originalRiskHash}}';
            NEW.caller_xid:=j#>>'{{certificate,callerXid}}';NEW.caller_pid:=(j#>>'{{certificate,callerPid}}')::integer;
            INSERT INTO {s}.identity_epoch(org_id,project_id,identity_id,purpose,key_hash,epoch,version,active)
                VALUES(NEW.org_id,NEW.project_id,NEW.identity_id,NEW.purpose,NEW.key_hash,1,1,true)
                ON CONFLICT(org_id,project_id,identity_id) DO UPDATE SET version=identity_epoch.version+1
                WHERE identity_epoch.active AND identity_epoch.purpose=EXCLUDED.purpose AND identity_epoch.key_hash=EXCLUDED.key_hash;
            IF NOT FOUND THEN RAISE EXCEPTION 'SHARED_PARENT_IDENTITY_BOUND_OR_REVOKED' USING ERRCODE='42501'; END IF;
            RETURN NEW; END $v3$''',
        f'ALTER FUNCTION {s}.derive_shared_parent_identity() OWNER TO {ISSUER_OWNER}',
        f'REVOKE ALL ON FUNCTION {s}.derive_shared_parent_identity() FROM PUBLIC,aos_runtime,aos_provider_capacity_issuer',
        f'CREATE TRIGGER shared_parent_binding_insert BEFORE INSERT ON {TABLE} FOR EACH ROW EXECUTE FUNCTION {s}.derive_shared_parent_identity()',
        f'CREATE TRIGGER shared_parent_binding_immutable BEFORE UPDATE OR DELETE ON {TABLE} FOR EACH ROW EXECUTE FUNCTION {s}.immutable_issuer_history()',
        f'CREATE TRIGGER shared_parent_binding_no_truncate BEFORE TRUNCATE ON {TABLE} FOR EACH STATEMENT EXECUTE FUNCTION {s}.immutable_issuer_history()',
    )


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _read_certificate(conn, *, expected_tenant, description, certificate_hash,
        root_hash, expected_root_epoch, expected_certificate_epoch):
    _require(type(conn) is psycopg.Connection and conn.info.transaction_status == TransactionStatus.INTRANS,
        'native v3 caller transaction required')
    _require(isinstance(expected_tenant, TenantContext), 'typed v3 tenant required')
    tenant = TenantContext.model_validate(_plain_contract_input(expected_tenant))
    _require((tenant.org_id, tenant.project_id) == ('org-org', 'dev-project'), 'positive v3 tenant required')
    _require(all(type(v) is str and re.fullmatch(r'[0-9a-f]{64}', v) for v in (certificate_hash, root_hash)),
        'exact persisted v3 certificate/root hashes required')
    _require(all(type(v) is int and v >= 1 for v in (expected_root_epoch, expected_certificate_epoch)),
        'native positive v3 metadata epochs required')
    prepared = SharedParentRiskDescriptionPreparation.model_validate(_plain_contract_input(description))
    _require((prepared.immutable.tenant.org_id,prepared.immutable.tenant.project_id) == (tenant.org_id,tenant.project_id), 'v3 description tenant drifted')
    with conn.cursor(row_factory=dict_row) as cur:
        context = cur.execute("""SELECT current_user AS role,current_setting('aos.org_id',true) AS org,
            current_setting('aos.project_id',true) AS project,current_setting('transaction_isolation') AS isolation,
            current_setting('TimeZone') AS timezone,pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid""").fetchone()
        _require((context['role'],context['org'],context['project'],context['isolation'],context['timezone']) ==
            (ISSUER_OWNER,tenant.org_id,tenant.project_id,'serializable','UTC'), 'exact private v3 SERIAL UTC caller required')
        plan_row = cur.execute(f'SELECT * FROM {SCHEMA}.manifest WHERE org_id=%s AND project_id=%s AND execution_id=%s',
            (tenant.org_id,tenant.project_id,prepared.plan_id)).fetchone()
        cert_row = cur.execute(f'SELECT * FROM {ISSUER_SCHEMA}.executor_certificate WHERE org_id=%s AND project_id=%s AND content_hash=%s',
            (tenant.org_id,tenant.project_id,certificate_hash)).fetchone()
        _require(cert_row is not None, 'persisted v3 certificate required')
        root_row = cur.execute(f'SELECT * FROM {ISSUER_SCHEMA}.issuer_root WHERE org_id=%s AND project_id=%s AND issuer_id=%s AND key_id=%s',
            (tenant.org_id,tenant.project_id,cert_row['issuer_id'],cert_row['key_id'])).fetchone()
    def parse(row, digest, model):
        _require(row is not None and isinstance(row['body'],(bytes,bytearray,memoryview)), 'persisted v3 original bytes required')
        raw = bytes(row['body'])
        _require(hashlib.sha256(raw).hexdigest() == row['content_hash'] == digest,
            'persisted v3 original hash drifted')
        item = model.model_validate_json(raw)
        _require(canonical_hash(item.model_dump(mode='json',by_alias=True)) == digest
            and (row['org_id'],row['project_id']) == (tenant.org_id,tenant.project_id), 'canonical v3 bytes/tenant required')
        return item
    plan = parse(plan_row,prepared.immutable.manifest_hash,ModelEvalTargetJudgeSharedRiskManifest)
    envelope = parse(cert_row,certificate_hash,ModelSharedParentRiskSignedCertificateEnvelope)
    root = parse(root_row,root_hash,ModelEvalIssuerVerificationInput)
    cert = envelope.certificate
    _require(plan == prepared.immutable.manifest and plan_row['execution_id'] == plan.execution_id
        and (cert_row['execution_id'],cert_row['case_id'],cert_row['purpose'],cert_row['attempt'],cert_row['issuer_id'],cert_row['key_id']) ==
        (plan.execution_id,cert.case_id,cert.purpose,1,cert.issuer_id,cert.issuer_key_id)
        and (root_row['issuer_id'],root_row['key_id']) == (root.issuer_id,root.issuer_key_id), 'exact v3 persisted column headers required')
    read_model_certificate_epoch(conn,expected_tenant=tenant,issuer_id=cert.issuer_id,issuer_key_id=cert.issuer_key_id,
        expected_epoch=expected_root_epoch,root_hash=root_hash,certificate_hash=certificate_hash,
        expected_certificate_epoch=expected_certificate_epoch,execution_id=plan.execution_id,case_id=cert.case_id,purpose=cert.purpose)
    _check_final(conn,prepared,envelope,root,context)
    return tenant,prepared,envelope,root,context


def _check_final(conn, description, envelope, root, context):
    with conn.cursor(row_factory=dict_row) as cur:
        final = cur.execute('SELECT clock_timestamp() AS now,pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
    _require((context['xid'],context['pid']) == (final['xid'],final['pid']), 'v3 private caller changed')
    validate_shared_parent_certificate_signature(description,envelope,issuer_input=root,
        checked_at=final['now'],revoked_identity_ids=frozenset())


def _lock_identity(conn, tenant, prepared, envelope, certificate_hash, expected_identity_epoch):
    _require(type(expected_identity_epoch) is int and expected_identity_epoch >= 1, 'native positive v3 identity epoch required')
    cert = envelope.certificate
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(f'''SELECT b.*,h.epoch,h.active FROM {TABLE} b JOIN {ISSUER_SCHEMA}.identity_epoch h
            ON (h.org_id,h.project_id,h.identity_id,h.purpose,h.key_hash)=(b.org_id,b.project_id,b.identity_id,b.purpose,b.key_hash)
            WHERE b.org_id=%s AND b.project_id=%s AND b.certificate_hash=%s FOR SHARE OF h''',
            (tenant.org_id,tenant.project_id,certificate_hash)).fetchone()
    _require(row is not None and row['active'] and row['epoch']==expected_identity_epoch
        and (row['identity_id'],row['purpose'],row['key_hash'],row['description_hash'],row['original_risk_hash'],row['caller_xid'],row['caller_pid']) ==
        (cert.leg.identity_id,cert.purpose,cert.leg.identity_key_hash,prepared.content_hash,
         prepared.immutable.original_risk_hash,prepared.immutable.caller_xid,prepared.immutable.caller_pid), 'v3 identity binding revoked or drifted')


def validate_persisted_shared_parent_identity(conn, *, expected_identity_epoch, **certificate_args):
    """Current necessary metadata only, never bootstrap/native risk/admission.

    Retains caller-owned root/certificate/identity locks and rechecks real time
    after every wait. No writes, role repair, commit, Source or transport.
    """
    try:
        tenant,prepared,envelope,root,context = _read_certificate(conn,**certificate_args)
        _lock_identity(conn,tenant,prepared,envelope,certificate_args['certificate_hash'],expected_identity_epoch)
        _check_final(conn,prepared,envelope,root,context)
    except psycopg.Error as exc:
        raise ValueError('persisted v3 identity metadata unavailable') from exc


def register_persisted_shared_parent_identity(conn, **certificate_args):
    """Private isolated registration of verified metadata; grants no trust."""
    try:
        tenant,prepared,envelope,root,context = _read_certificate(conn,**certificate_args)
        existing = conn.execute(f'SELECT 1 FROM {TABLE} WHERE org_id=%s AND project_id=%s AND certificate_hash=%s',
            (tenant.org_id,tenant.project_id,certificate_args['certificate_hash'])).fetchone()
        if existing is None:
            conn.execute(f'INSERT INTO {TABLE}(org_id,project_id,certificate_hash) VALUES (%s,%s,%s)',
                (tenant.org_id,tenant.project_id,certificate_args['certificate_hash']))
        _lock_identity(conn,tenant,prepared,envelope,certificate_args['certificate_hash'],1)
        _check_final(conn,prepared,envelope,root,context)
    except psycopg.Error as exc:
        raise ValueError('v3 identity registration rejected') from exc

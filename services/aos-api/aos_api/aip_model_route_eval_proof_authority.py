"""Revalidate current Route proof signers; never grant execution or release."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import base64
import hashlib
import json
import re

from aos_api.aip_model_route_eval_finalization_proof import (
    RouteEvalFinalizationProof,
    canonical_route_eval_finalization_proof,
)
from aos_api.aip_model_route_eval_signatures import (
    validate_governed_certificate_signature,
)
from aos_api.aip_eval_contracts import AssetType, EvalReportRevision
from aos_api.aip_provider_capacity_source_contracts import (
    ProviderCapacityConsumptionCommand,
)
from aos_api.tenant_scope import TenantScope


ISSUER_OWNER = "aos_model_route_eval_issuer_owner"
ISSUER_READER = "aos_model_route_eval_issuer_reader"
ISSUER_SCHEMA = "aos_model_route_eval_issuer_private"
SESSION = "aos_model_route_eval"
READER_BODY_HASHES = {
    "read_current_executor_certificate": "71bdc34a4c9e3990694373e1d0f203ed8762e68a9dc75f272043d0dccfaf7264",
    "read_current_issuer_root": "db737a8c5eedf6dadf0c4437ca3c67e2a0db9d77f05ea649016bc9044574b7b3",
}


class RouteEvalProofAuthorityRejected(RuntimeError):
    """Safe fail-closed category without keys, signatures or manifest bytes."""


class RouteEvalReleaseEvidenceRejected(RuntimeError):
    """Safe combined-consumer rejection without Source credentials or payloads."""


@dataclass(frozen=True)
class VerifiedRouteEvalProofSigners:
    execution_id: str
    manifest_hash: str
    identity_ids: tuple[str, ...]
    issuer_keys: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class VerifiedRouteEvalProofAuthority:
    execution_id: str
    manifest_hash: str
    issuer_epochs: tuple[tuple[str, str, int, str], ...]
    certificate_epochs: tuple[tuple[str, int], ...]
    checked_at: datetime
    caller_xid: str
    caller_pid: int
    execution_allowed: bool = False


@dataclass(frozen=True)
class RouteEvalReleaseEvidence:
    manifest_bytes: bytes
    source_commands: tuple[ProviderCapacityConsumptionCommand, ...]


@dataclass(frozen=True)
class VerifiedRouteEvalReleaseEvidence:
    execution_id: str
    report_id: str
    report_hash: str
    manifest_hash: str
    source_count: int
    publication_epoch: int | None
    checked_at: datetime
    caller_xid: str
    caller_pid: int
    release_allowed: bool = False


def install_closed_route_eval_proof_authority(execute) -> None:
    """Install an empty Route-only authority substrate without a writer/login.

    The caller must be the future migration's privileged executor.  Re-running
    deliberately fails instead of accepting role, schema, ACL or table drift.
    """
    execute(f"CREATE ROLE {ISSUER_OWNER} NOLOGIN NOINHERIT NOSUPERUSER "
            "NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION")
    execute(f"CREATE ROLE {ISSUER_READER} NOLOGIN NOINHERIT NOSUPERUSER "
            "NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION")
    execute(f"CREATE SCHEMA {ISSUER_SCHEMA} AUTHORIZATION {ISSUER_OWNER}")
    execute(f"REVOKE ALL ON SCHEMA {ISSUER_SCHEMA} FROM PUBLIC")
    execute(f"GRANT USAGE ON SCHEMA {ISSUER_SCHEMA} TO {ISSUER_READER}")
    execute(f"ALTER DEFAULT PRIVILEGES FOR ROLE {ISSUER_OWNER} IN SCHEMA "
            f"{ISSUER_SCHEMA} REVOKE ALL ON TABLES FROM PUBLIC")
    execute(f"ALTER DEFAULT PRIVILEGES FOR ROLE {ISSUER_OWNER} IN SCHEMA "
            f"{ISSUER_SCHEMA} REVOKE ALL ON FUNCTIONS FROM PUBLIC")
    execute(f"""CREATE FUNCTION {ISSUER_SCHEMA}.immutable_history() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $body$ BEGIN
        RAISE EXCEPTION 'ROUTE_EVAL_ISSUER_HISTORY_IMMUTABLE' USING ERRCODE='42501';
      END $body$""")
    execute(f"ALTER FUNCTION {ISSUER_SCHEMA}.immutable_history() OWNER TO {ISSUER_OWNER}")
    execute(f"REVOKE ALL ON FUNCTION {ISSUER_SCHEMA}.immutable_history() FROM PUBLIC")

    scope = "org_id text NOT NULL CHECK(org_id='org-org'),project_id text NOT NULL CHECK(project_id='dev-project')"
    execute(f"""CREATE TABLE {ISSUER_SCHEMA}.issuer_root(
      {scope},issuer_id text NOT NULL CHECK(length(issuer_id) BETWEEN 1 AND 200 AND issuer_id=btrim(issuer_id)),
      issuer_key_id text NOT NULL CHECK(length(issuer_key_id) BETWEEN 1 AND 200 AND issuer_key_id=btrim(issuer_key_id)),
      input_hash text NOT NULL CHECK(input_hash ~ '^[0-9a-f]{{64}}$'),
      public_key_hash text NOT NULL CHECK(public_key_hash ~ '^[0-9a-f]{{64}}$'),
      body bytea NOT NULL CHECK(octet_length(body) BETWEEN 2 AND 65536),
      valid_from timestamptz NOT NULL,valid_until timestamptz NOT NULL,
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,issuer_id,issuer_key_id),
      UNIQUE(org_id,project_id,input_hash),CHECK(valid_from<valid_until))""")
    execute(f"""CREATE TABLE {ISSUER_SCHEMA}.executor_certificate(
      {scope},execution_id text NOT NULL CHECK(length(execution_id) BETWEEN 1 AND 200 AND execution_id=btrim(execution_id)),
      case_id text NOT NULL CHECK(length(case_id) BETWEEN 1 AND 200 AND case_id=btrim(case_id)),
      purpose text NOT NULL CHECK(purpose IN ('target','judge')),
      identity_id text NOT NULL CHECK(length(identity_id) BETWEEN 1 AND 200 AND identity_id=btrim(identity_id)),
      identity_key_hash text NOT NULL CHECK(identity_key_hash ~ '^[0-9a-f]{{64}}$'),
      issuer_id text NOT NULL,issuer_key_id text NOT NULL,
      manifest_hash text NOT NULL CHECK(manifest_hash ~ '^[0-9a-f]{{64}}$'),
      certificate_hash text NOT NULL CHECK(certificate_hash ~ '^[0-9a-f]{{64}}$'),
      body bytea NOT NULL CHECK(octet_length(body) BETWEEN 2 AND 131072),
      valid_from timestamptz NOT NULL,valid_until timestamptz NOT NULL,
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,certificate_hash),
      UNIQUE(org_id,project_id,execution_id,case_id,purpose),
      FOREIGN KEY(org_id,project_id,issuer_id,issuer_key_id)
        REFERENCES {ISSUER_SCHEMA}.issuer_root(org_id,project_id,issuer_id,issuer_key_id),
      CHECK(valid_from<valid_until))""")
    execute(f"""CREATE TABLE {ISSUER_SCHEMA}.issuer_epoch(
      {scope},issuer_id text NOT NULL,issuer_key_id text NOT NULL,
      epoch bigint NOT NULL CHECK(epoch>=1),active_hash text CHECK(active_hash ~ '^[0-9a-f]{{64}}$'),
      updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,issuer_id,issuer_key_id),
      FOREIGN KEY(org_id,project_id,issuer_id,issuer_key_id)
        REFERENCES {ISSUER_SCHEMA}.issuer_root(org_id,project_id,issuer_id,issuer_key_id))""")
    execute(f"""CREATE TABLE {ISSUER_SCHEMA}.certificate_epoch(
      {scope},certificate_hash text NOT NULL CHECK(certificate_hash ~ '^[0-9a-f]{{64}}$'),
      epoch bigint NOT NULL CHECK(epoch>=1),active_hash text CHECK(active_hash=certificate_hash),
      updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,certificate_hash),
      FOREIGN KEY(org_id,project_id,certificate_hash)
        REFERENCES {ISSUER_SCHEMA}.executor_certificate(org_id,project_id,certificate_hash))""")
    execute(f"""CREATE TABLE {ISSUER_SCHEMA}.authority_withdrawal(
      {scope},event_id text NOT NULL CHECK(length(event_id) BETWEEN 1 AND 200 AND event_id=btrim(event_id)),
      target_kind text NOT NULL CHECK(target_kind IN ('issuer_root','executor_certificate')),
      issuer_id text,issuer_key_id text,certificate_hash text CHECK(certificate_hash ~ '^[0-9a-f]{{64}}$'),
      content_hash text NOT NULL CHECK(content_hash ~ '^[0-9a-f]{{64}}$'),
      body bytea NOT NULL CHECK(octet_length(body) BETWEEN 2 AND 65536),
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,event_id),
      CHECK((target_kind='issuer_root' AND issuer_id IS NOT NULL AND issuer_key_id IS NOT NULL AND certificate_hash IS NULL)
         OR (target_kind='executor_certificate' AND issuer_id IS NULL AND issuer_key_id IS NULL AND certificate_hash IS NOT NULL)))""")

    execute(f"""CREATE FUNCTION {ISSUER_SCHEMA}.issuer_epoch_transition() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $body$ BEGIN
        IF (TG_OP='INSERT' AND (NEW.epoch<>1 OR NEW.active_hash IS NULL)) OR
           (TG_OP='UPDATE' AND ((NEW.org_id,NEW.project_id,NEW.issuer_id,NEW.issuer_key_id)
             IS DISTINCT FROM (OLD.org_id,OLD.project_id,OLD.issuer_id,OLD.issuer_key_id)
             OR NEW.epoch<>OLD.epoch+1 OR OLD.active_hash IS NULL OR NEW.active_hash IS NOT NULL))
        THEN RAISE EXCEPTION 'ROUTE_EVAL_ISSUER_EPOCH_TRANSITION' USING ERRCODE='42501'; END IF;
        NEW.updated_at:=clock_timestamp();RETURN NEW;
      END $body$;
      CREATE FUNCTION {ISSUER_SCHEMA}.certificate_epoch_transition() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $body$ BEGIN
        IF (TG_OP='INSERT' AND (NEW.epoch<>1 OR NEW.active_hash IS NULL OR NEW.active_hash<>NEW.certificate_hash)) OR
           (TG_OP='UPDATE' AND ((NEW.org_id,NEW.project_id,NEW.certificate_hash)
             IS DISTINCT FROM (OLD.org_id,OLD.project_id,OLD.certificate_hash)
             OR NEW.epoch<>OLD.epoch+1 OR OLD.active_hash IS NULL OR NEW.active_hash IS NOT NULL))
        THEN RAISE EXCEPTION 'ROUTE_EVAL_CERTIFICATE_EPOCH_TRANSITION' USING ERRCODE='42501'; END IF;
        NEW.updated_at:=clock_timestamp();RETURN NEW;
      END $body$""")
    execute(f"""CREATE FUNCTION {ISSUER_SCHEMA}.initialize_issuer_epoch() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $body$ BEGIN
        PERFORM pg_advisory_xact_lock(hashtext('route-eval-root'),hashtext(NEW.issuer_id||chr(31)||NEW.issuer_key_id));
        INSERT INTO {ISSUER_SCHEMA}.issuer_epoch(org_id,project_id,issuer_id,issuer_key_id,epoch,active_hash)
          VALUES(NEW.org_id,NEW.project_id,NEW.issuer_id,NEW.issuer_key_id,1,NEW.input_hash);
        RETURN NULL;
      END $body$;
      CREATE FUNCTION {ISSUER_SCHEMA}.initialize_certificate_epoch() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $body$ BEGIN
        PERFORM pg_advisory_xact_lock_shared(hashtext('route-eval-root'),hashtext(NEW.issuer_id||chr(31)||NEW.issuer_key_id));
        PERFORM 1 FROM {ISSUER_SCHEMA}.issuer_epoch WHERE org_id=NEW.org_id AND project_id=NEW.project_id
          AND issuer_id=NEW.issuer_id AND issuer_key_id=NEW.issuer_key_id AND active_hash IS NOT NULL;
        IF NOT FOUND THEN RAISE EXCEPTION 'ROUTE_EVAL_ACTIVE_ROOT_REQUIRED' USING ERRCODE='42501'; END IF;
        PERFORM pg_advisory_xact_lock(hashtext('route-eval-certificate'),hashtext(NEW.certificate_hash));
        INSERT INTO {ISSUER_SCHEMA}.certificate_epoch(org_id,project_id,certificate_hash,epoch,active_hash)
          VALUES(NEW.org_id,NEW.project_id,NEW.certificate_hash,1,NEW.certificate_hash);
        RETURN NULL;
      END $body$""")
    execute(f"""CREATE FUNCTION {ISSUER_SCHEMA}.advance_withdrawal() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $body$ BEGIN
        IF NEW.target_kind='issuer_root' THEN
          PERFORM pg_advisory_xact_lock(hashtext('route-eval-root'),hashtext(NEW.issuer_id||chr(31)||NEW.issuer_key_id));
          UPDATE {ISSUER_SCHEMA}.issuer_epoch SET epoch=epoch+1,active_hash=NULL
            WHERE org_id=NEW.org_id AND project_id=NEW.project_id AND issuer_id=NEW.issuer_id
              AND issuer_key_id=NEW.issuer_key_id AND active_hash IS NOT NULL;
        ELSE
          PERFORM pg_advisory_xact_lock(hashtext('route-eval-certificate'),hashtext(NEW.certificate_hash));
          UPDATE {ISSUER_SCHEMA}.certificate_epoch SET epoch=epoch+1,active_hash=NULL
            WHERE org_id=NEW.org_id AND project_id=NEW.project_id
              AND certificate_hash=NEW.certificate_hash AND active_hash IS NOT NULL;
        END IF;
        IF NOT FOUND THEN RAISE EXCEPTION 'ROUTE_EVAL_WITHDRAWAL_CURRENT_HEAD_REQUIRED' USING ERRCODE='42501'; END IF;
        RETURN NEW;
      END $body$""")

    functions=("issuer_epoch_transition","certificate_epoch_transition",
               "initialize_issuer_epoch","initialize_certificate_epoch","advance_withdrawal")
    for name in functions:
        execute(f"ALTER FUNCTION {ISSUER_SCHEMA}.{name}() OWNER TO {ISSUER_OWNER}")
        execute(f"REVOKE ALL ON FUNCTION {ISSUER_SCHEMA}.{name}() FROM PUBLIC")
    for table in ("issuer_root","executor_certificate","issuer_epoch",
                  "certificate_epoch","authority_withdrawal"):
        relation=f"{ISSUER_SCHEMA}.{table}"
        execute(f"ALTER TABLE {relation} OWNER TO {ISSUER_OWNER}")
        execute(f"REVOKE ALL ON {relation} FROM PUBLIC")
        execute(f"ALTER TABLE {relation} ENABLE ROW LEVEL SECURITY")
        execute(f"ALTER TABLE {relation} FORCE ROW LEVEL SECURITY")
        execute(f"CREATE POLICY route_eval_owner_scope ON {relation} TO {ISSUER_OWNER} "
                "USING(org_id=NULLIF(current_setting('aos.org_id',true),'') AND "
                "project_id=NULLIF(current_setting('aos.project_id',true),'')) WITH CHECK("
                "org_id=NULLIF(current_setting('aos.org_id',true),'') AND "
                "project_id=NULLIF(current_setting('aos.project_id',true),''))")
        execute(f"CREATE POLICY route_eval_reader_scope ON {relation} FOR SELECT TO {ISSUER_READER} "
                "USING(org_id=NULLIF(current_setting('aos.org_id',true),'') AND "
                "project_id=NULLIF(current_setting('aos.project_id',true),''))")
        execute(f"GRANT SELECT ON {relation} TO {ISSUER_READER}")
    execute(f"""CREATE FUNCTION {ISSUER_SCHEMA}.read_current_issuer_root(
      p_org_id text,p_project_id text,p_issuer_id text,p_issuer_key_id text)
      RETURNS TABLE(input_hash text,public_key_hash text,body bytea,valid_from timestamptz,
        valid_until timestamptz,epoch bigint,active_hash text)
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body$ BEGIN
        IF session_user<>'{SESSION}' OR current_setting('role',true)<>'aos_runtime'
          OR current_setting('aos.org_id',true)<>p_org_id
          OR current_setting('aos.project_id',true)<>p_project_id
          OR p_org_id<>'org-org' OR p_project_id<>'dev-project'
          OR current_setting('transaction_isolation')<>'serializable'
          OR current_setting('transaction_read_only')<>'off'
          OR p_issuer_id IS NULL OR p_issuer_id<>btrim(p_issuer_id)
          OR length(p_issuer_id) NOT BETWEEN 1 AND 200
          OR p_issuer_key_id IS NULL OR p_issuer_key_id<>btrim(p_issuer_key_id)
          OR length(p_issuer_key_id) NOT BETWEEN 1 AND 200
        THEN RAISE EXCEPTION 'ROUTE_EVAL_EXACT_RUNTIME_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
        PERFORM pg_catalog.pg_advisory_xact_lock_shared(pg_catalog.hashtext('route-eval-root'),
          pg_catalog.hashtext(p_issuer_id||chr(31)||p_issuer_key_id));
        RETURN QUERY SELECT r.input_hash,r.public_key_hash,r.body,r.valid_from,r.valid_until,
          e.epoch,e.active_hash FROM {ISSUER_SCHEMA}.issuer_root r
          JOIN {ISSUER_SCHEMA}.issuer_epoch e USING(org_id,project_id,issuer_id,issuer_key_id)
          WHERE r.org_id=p_org_id AND r.project_id=p_project_id
            AND r.issuer_id=p_issuer_id AND r.issuer_key_id=p_issuer_key_id;
      END $body$;
      CREATE FUNCTION {ISSUER_SCHEMA}.read_current_executor_certificate(
      p_org_id text,p_project_id text,p_certificate_hash text)
      RETURNS TABLE(execution_id text,case_id text,purpose text,identity_id text,
        identity_key_hash text,issuer_id text,issuer_key_id text,manifest_hash text,
        certificate_hash text,body bytea,valid_from timestamptz,valid_until timestamptz,
        epoch bigint,active_hash text)
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body$ BEGIN
        IF session_user<>'{SESSION}' OR current_setting('role',true)<>'aos_runtime'
          OR current_setting('aos.org_id',true)<>p_org_id
          OR current_setting('aos.project_id',true)<>p_project_id
          OR p_org_id<>'org-org' OR p_project_id<>'dev-project'
          OR current_setting('transaction_isolation')<>'serializable'
          OR current_setting('transaction_read_only')<>'off'
          OR p_certificate_hash IS NULL OR p_certificate_hash!~'^[0-9a-f]{{64}}$'
        THEN RAISE EXCEPTION 'ROUTE_EVAL_EXACT_RUNTIME_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
        PERFORM pg_catalog.pg_advisory_xact_lock_shared(
          pg_catalog.hashtext('route-eval-certificate'),pg_catalog.hashtext(p_certificate_hash));
        RETURN QUERY SELECT c.execution_id,c.case_id,c.purpose,c.identity_id,c.identity_key_hash,
          c.issuer_id,c.issuer_key_id,c.manifest_hash,c.certificate_hash,c.body,c.valid_from,
          c.valid_until,e.epoch,e.active_hash FROM {ISSUER_SCHEMA}.executor_certificate c
          JOIN {ISSUER_SCHEMA}.certificate_epoch e USING(org_id,project_id,certificate_hash)
          WHERE c.org_id=p_org_id AND c.project_id=p_project_id
            AND c.certificate_hash=p_certificate_hash;
      END $body$""")
    for name,args in (("read_current_issuer_root","text,text,text,text"),
                      ("read_current_executor_certificate","text,text,text")):
        execute(f"ALTER FUNCTION {ISSUER_SCHEMA}.{name}({args}) OWNER TO {ISSUER_READER}")
        execute(f"REVOKE ALL ON FUNCTION {ISSUER_SCHEMA}.{name}({args}) FROM PUBLIC")
        execute(f"GRANT EXECUTE ON FUNCTION {ISSUER_SCHEMA}.{name}({args}) TO aos_runtime")
    execute(f"GRANT USAGE ON SCHEMA {ISSUER_SCHEMA} TO aos_runtime")
    for table in ("issuer_root","executor_certificate","authority_withdrawal"):
        execute(f"CREATE TRIGGER immutable_route_eval_history BEFORE UPDATE OR DELETE ON "
                f"{ISSUER_SCHEMA}.{table} FOR EACH ROW EXECUTE FUNCTION {ISSUER_SCHEMA}.immutable_history()")
        execute(f"CREATE TRIGGER immutable_route_eval_truncate BEFORE TRUNCATE ON "
                f"{ISSUER_SCHEMA}.{table} FOR EACH STATEMENT EXECUTE FUNCTION {ISSUER_SCHEMA}.immutable_history()")
    execute(f"CREATE TRIGGER route_eval_issuer_epoch_transition BEFORE INSERT OR UPDATE ON "
            f"{ISSUER_SCHEMA}.issuer_epoch FOR EACH ROW EXECUTE FUNCTION {ISSUER_SCHEMA}.issuer_epoch_transition()")
    execute(f"CREATE TRIGGER route_eval_certificate_epoch_transition BEFORE INSERT OR UPDATE ON "
            f"{ISSUER_SCHEMA}.certificate_epoch FOR EACH ROW EXECUTE FUNCTION {ISSUER_SCHEMA}.certificate_epoch_transition()")
    for table in ("issuer_epoch","certificate_epoch"):
        execute(f"CREATE TRIGGER immutable_route_eval_epoch_delete BEFORE DELETE ON {ISSUER_SCHEMA}.{table} "
                f"FOR EACH ROW EXECUTE FUNCTION {ISSUER_SCHEMA}.immutable_history()")
        execute(f"CREATE TRIGGER immutable_route_eval_epoch_truncate BEFORE TRUNCATE ON {ISSUER_SCHEMA}.{table} "
                f"FOR EACH STATEMENT EXECUTE FUNCTION {ISSUER_SCHEMA}.immutable_history()")
    execute(f"CREATE TRIGGER initialize_route_eval_issuer_epoch AFTER INSERT ON {ISSUER_SCHEMA}.issuer_root "
            f"FOR EACH ROW EXECUTE FUNCTION {ISSUER_SCHEMA}.initialize_issuer_epoch()")
    execute(f"CREATE TRIGGER initialize_route_eval_certificate_epoch AFTER INSERT ON {ISSUER_SCHEMA}.executor_certificate "
            f"FOR EACH ROW EXECUTE FUNCTION {ISSUER_SCHEMA}.initialize_certificate_epoch()")
    execute(f"CREATE TRIGGER advance_route_eval_withdrawal BEFORE INSERT ON {ISSUER_SCHEMA}.authority_withdrawal "
            f"FOR EACH ROW EXECUTE FUNCTION {ISSUER_SCHEMA}.advance_withdrawal()")


def _authority_boundary(conn, scope: TenantScope) -> dict:
    from aos_api.aip_model_route_eval_owner import _require_native_connection

    _require_native_connection(conn)
    row=conn.execute("""SELECT pg_catalog.current_database() AS database,
      (SELECT oid FROM pg_catalog.pg_database WHERE datname=pg_catalog.current_database()) AS database_oid,
      session_user AS login,current_user AS role,
      pg_catalog.current_setting('aos.org_id',true) AS org_id,
      pg_catalog.current_setting('aos.project_id',true) AS project_id,
      pg_catalog.current_setting('transaction_isolation') AS isolation,
      pg_catalog.current_setting('transaction_read_only') AS readonly,
      pg_catalog.pg_current_xact_id()::text AS xid,pg_catalog.pg_backend_pid() AS pid,
      pg_catalog.clock_timestamp() AS now""").fetchone()
    if (type(row) is not dict or type(row.get('database')) is not str
        or re.fullmatch(r'[a-z][a-z0-9_]{0,62}',row['database']) is None
        or type(row.get('database_oid')) is not int or isinstance(row['database_oid'],bool) or row['database_oid']<1
        or (row.get('login'),row.get('role'),row.get('org_id'),row.get('project_id'),
            row.get('isolation'),row.get('readonly'))!=(SESSION,'aos_runtime',*scope.key,'serializable','off')
        or type(row.get('xid')) is not str or re.fullmatch(r'[1-9][0-9]*',row['xid']) is None
        or type(row.get('pid')) is not int or isinstance(row['pid'],bool) or row['pid']<1
        or type(row.get('now')) is not datetime or row['now'].utcoffset() is None):
        raise ValueError('exact Route proof authority caller required')
    return row


def _audit_authority_contract(conn) -> None:
    functions=conn.execute(f"""SELECT p.proname,owner_role.rolname AS owner,p.prosecdef,
      p.proconfig,p.prosrc AS body,
      pg_catalog.has_function_privilege('aos_runtime',p.oid,'EXECUTE') AS runtime_execute,
      NOT EXISTS(SELECT 1 FROM pg_catalog.aclexplode(COALESCE(p.proacl,
        pg_catalog.acldefault('f',p.proowner))) acl WHERE acl.grantee=0
        AND acl.privilege_type='EXECUTE') AS public_revoked,
      NOT EXISTS(SELECT 1 FROM pg_catalog.aclexplode(COALESCE(p.proacl,
        pg_catalog.acldefault('f',p.proowner))) acl WHERE acl.privilege_type<>'EXECUTE'
        OR acl.grantee NOT IN (p.proowner,(SELECT oid FROM pg_catalog.pg_roles
          WHERE rolname='aos_runtime'))) AS exact_acl
      FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
      JOIN pg_catalog.pg_roles owner_role ON owner_role.oid=p.proowner
      WHERE n.nspname=%s AND p.proname IN
        ('read_current_issuer_root','read_current_executor_certificate')
      ORDER BY p.proname""",(ISSUER_SCHEMA,)).fetchall()
    if (type(functions) is not list or len(functions)!=2):raise ValueError
    for row in functions:
        name=row.get('proname') if type(row) is dict else None
        if (name not in READER_BODY_HASHES or row.get('owner')!=ISSUER_READER
            or row.get('prosecdef') is not True or row.get('proconfig')!=['search_path=pg_catalog']
            or type(row.get('body')) is not str
            or hashlib.sha256(row['body'].encode()).hexdigest()!=READER_BODY_HASHES[name]
            or row.get('runtime_execute') is not True or row.get('public_revoked') is not True
            or row.get('exact_acl') is not True):raise ValueError
    role=conn.execute("""SELECT rolcanlogin,rolinherit,rolsuper,rolbypassrls,rolcreatedb,
      rolcreaterole,rolreplication,
      (SELECT count(*) FROM pg_catalog.pg_auth_members m WHERE m.member=r.oid
        OR m.roleid=r.oid) AS membership_edges,
      (SELECT count(*) FROM pg_catalog.pg_class c WHERE c.relowner=r.oid) AS owned_relations,
      (SELECT count(*) FROM pg_catalog.pg_namespace n WHERE n.nspowner=r.oid) AS owned_schemas,
      (SELECT count(*) FROM pg_catalog.pg_database d WHERE d.datdba=r.oid) AS owned_databases
      FROM pg_catalog.pg_roles r WHERE r.rolname=%s""",(ISSUER_READER,)).fetchone()
    if (type(role) is not dict or tuple(role.get(key) for key in ('rolcanlogin','rolinherit',
        'rolsuper','rolbypassrls','rolcreatedb','rolcreaterole','rolreplication'))!=(False,)*7
        or tuple(role.get(key) for key in ('membership_edges','owned_relations','owned_schemas',
            'owned_databases'))!=(0,0,0,0)):raise ValueError
    privileges=conn.execute(f"""SELECT count(*) FILTER(WHERE
      pg_catalog.has_table_privilege('aos_runtime',format('%%I.%%I',n.nspname,c.relname),'SELECT'))
      AS runtime_table_selects FROM pg_catalog.pg_class c
      JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
      WHERE n.nspname=%s AND c.relname IN ('issuer_root','executor_certificate',
        'issuer_epoch','certificate_epoch','authority_withdrawal')""",(ISSUER_SCHEMA,)).fetchone()
    if type(privileges) is not dict or privileges.get('runtime_table_selects')!=0:raise ValueError


def _canonical_json_bytes(value) -> bytes:
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,
                      allow_nan=False).encode()


def read_current_route_eval_proof_authority(
    conn,*,scope: TenantScope,proof: RouteEvalFinalizationProof,manifest_bytes: bytes,
) -> VerifiedRouteEvalProofAuthority:
    """Lock and revalidate current Route roots/certificates in caller transaction."""
    try:
        if (type(scope) is not TenantScope or scope.key!=('org-org','dev-project')
            or type(proof) is not RouteEvalFinalizationProof
            or (proof.tenant.org_id,proof.tenant.project_id)!=scope.key
            or type(manifest_bytes) is not bytes
            or hashlib.sha256(manifest_bytes).hexdigest()!=proof.manifest_hash):
            raise ValueError
        canonical_route_eval_finalization_proof(proof)
        before=_authority_boundary(conn,scope)
        _audit_authority_contract(conn)
        roots={}
        certificates={}
        for item in proof.calls:
            root=item.issuer_input;signed=item.signed_certificate;certificate=signed.certificate
            root_payload=root.model_dump(mode='json',by_alias=True)
            signed_payload=signed.model_dump(mode='json',by_alias=True)
            root_key=(root.issuer_id,root.issuer_key_id)
            root_expected=(item.issuer_input_hash,_canonical_json_bytes(root_payload),
                hashlib.sha256(base64.b64decode(root.public_key_base64,validate=True)).hexdigest(),
                root.valid_from,root.valid_until)
            if root_key in roots and roots[root_key]!=root_expected:raise ValueError
            roots[root_key]=root_expected
            cert_expected=(item.certificate_hash,_canonical_json_bytes(signed_payload),certificate)
            if item.certificate_hash in certificates and certificates[item.certificate_hash]!=cert_expected:
                raise ValueError
            certificates[item.certificate_hash]=cert_expected
        issuer_epochs=[]
        for issuer_id,key_id in sorted(roots):
            row=conn.execute(f"SELECT * FROM {ISSUER_SCHEMA}.read_current_issuer_root(%s,%s,%s,%s)",
                (*scope.key,issuer_id,key_id)).fetchone()
            input_hash,body,key_hash,valid_from,valid_until=roots[(issuer_id,key_id)]
            if (type(row) is not dict or row.get('input_hash')!=input_hash or row.get('body')!=body
                or row.get('public_key_hash')!=key_hash or row.get('valid_from')!=valid_from
                or row.get('valid_until')!=valid_until or type(row.get('epoch')) is not int
                or isinstance(row.get('epoch'),bool) or row['epoch']<1 or row.get('active_hash')!=input_hash):
                raise ValueError
            issuer_epochs.append((issuer_id,key_id,row['epoch'],input_hash))
        certificate_epochs=[]
        for certificate_hash in sorted(certificates):
            row=conn.execute(f"SELECT * FROM {ISSUER_SCHEMA}.read_current_executor_certificate(%s,%s,%s)",
                (*scope.key,certificate_hash)).fetchone()
            _,body,certificate=certificates[certificate_hash]
            expected=(certificate.execution_id,certificate.case_id,certificate.purpose,certificate.identity_id,
                certificate.identity_key_hash,certificate.issuer_id,certificate.issuer_key_id,
                certificate.manifest_hash,certificate_hash,body,certificate.valid_from,certificate.valid_until)
            actual=tuple(row.get(key) for key in ('execution_id','case_id','purpose','identity_id',
                'identity_key_hash','issuer_id','issuer_key_id','manifest_hash','certificate_hash','body',
                'valid_from','valid_until')) if type(row) is dict else ()
            if (actual!=expected or type(row.get('epoch')) is not int or isinstance(row.get('epoch'),bool)
                or row['epoch']<1 or row.get('active_hash')!=certificate_hash):raise ValueError
            certificate_epochs.append((certificate_hash,row['epoch']))
        after=_authority_boundary(conn,scope)
        if (any(after.get(k)!=v for k,v in before.items() if k!='now') or after['now']<before['now']
            or after['now']<proof.finalized_at
            or any(not valid_from<=after['now']<valid_until for _,_,_,valid_from,valid_until in roots.values())
            or any(not cert.valid_from<=after['now']<cert.valid_until for _,_,cert in certificates.values())):
            raise ValueError
        revalidate_route_eval_proof_signers(scope=scope,proof=proof,manifest_bytes=manifest_bytes,
            checked_at=after['now'],revoked_identity_ids=frozenset())
        return VerifiedRouteEvalProofAuthority(execution_id=proof.execution_id,
            manifest_hash=proof.manifest_hash,issuer_epochs=tuple(issuer_epochs),
            certificate_epochs=tuple(certificate_epochs),checked_at=after['now'],
            caller_xid=after['xid'],caller_pid=after['pid'])
    except RouteEvalProofAuthorityRejected:
        raise
    except Exception as exc:
        raise RouteEvalProofAuthorityRejected('current Route proof authority required') from exc


def verify_route_eval_release_evidence(
    conn,
    *,
    scope: TenantScope,
    report: EvalReportRevision,
    evidence: RouteEvalReleaseEvidence,
    publication_id: str | None = None,
) -> VerifiedRouteEvalReleaseEvidence:
    """Verify Route Source, persisted proof, current authority/subject and optional epoch.

    The caller retains one SERIALIZABLE transaction and owns commit/rollback.
    Source commands remain ephemeral and are never returned or persisted here.
    """
    try:
        if (
            type(scope) is not TenantScope
            or scope.key != ("org-org", "dev-project")
            or type(report) is not EvalReportRevision
            or (report.tenant.org_id, report.tenant.project_id) != scope.key
            or report.target.asset_type is not AssetType.MODEL_ROUTE
            or type(evidence) is not RouteEvalReleaseEvidence
            or type(evidence.manifest_bytes) is not bytes
            or type(evidence.source_commands) is not tuple
            or not evidence.source_commands
            or any(
                type(command) is not ProviderCapacityConsumptionCommand
                for command in evidence.source_commands
            )
            or (
                publication_id is not None
                and (
                    type(publication_id) is not str
                    or publication_id != publication_id.strip()
                    or not 1 <= len(publication_id) <= 200
                )
            )
        ):
            raise ValueError
        before = _authority_boundary(conn, scope)
        from aos_api.aip_model_route_eval_owner import (
            prepare_governed_eval_native_sources,
        )
        from aos_api.aip_model_route_eval_proof_reader import (
            read_current_route_eval_subject,
        )
        from aos_api.aip_model_route_eval_publication_epoch import (
            lock_eval_publication_epoch,
        )
        from aos_api.aip_model_route_eval_report_proof_reader import (
            read_verified_route_eval_report_from_persistence,
        )

        source_prefix = prepare_governed_eval_native_sources(
            conn,
            expected_database=before["database"],
            manifest_bytes=evidence.manifest_bytes,
            commands=evidence.source_commands,
        )
        if type(source_prefix) is not bytes or not source_prefix:
            raise ValueError
        report_proof = read_verified_route_eval_report_from_persistence(
            conn, scope=scope, report=report
        )
        proof = report_proof.proof
        authority = read_current_route_eval_proof_authority(
            conn,
            scope=scope,
            proof=proof,
            manifest_bytes=evidence.manifest_bytes,
        )
        subject = read_current_route_eval_subject(
            conn,
            scope=scope,
            proof=proof,
            manifest_bytes=evidence.manifest_bytes,
        )
        target = (
            report.target.asset_id,
            str(report.target.revision),
            report.target.content_hash,
        )
        current = (
            subject.target_ref.asset_id,
            str(subject.target_ref.revision),
            subject.target_ref.content_hash,
        )
        if (
            target != current
            or report_proof.report_id != report.report_id
            or report_proof.report_hash != report.content_hash
            or (
                proof.execution_id,
                proof.report_id,
                proof.report_revision,
                proof.report_hash,
            )
            != (
                authority.execution_id,
                report.report_id,
                report.revision,
                report.content_hash,
            )
            or (subject.execution_id, subject.manifest_hash)
            != (proof.execution_id, proof.manifest_hash)
        ):
            raise ValueError
        epoch = (
            None
            if publication_id is None
            else lock_eval_publication_epoch(conn, scope, publication_id)
        )
        after = _authority_boundary(conn, scope)
        if (
            any(
                after.get(key) != value
                for key, value in before.items()
                if key != "now"
            )
            or after["now"] < before["now"]
            or after["now"] < authority.checked_at
            or after["now"] < subject.checked_at
            or type(epoch) not in {int, type(None)}
            or isinstance(epoch, bool)
            or (epoch is not None and epoch < 1)
        ):
            raise ValueError
        return VerifiedRouteEvalReleaseEvidence(
            execution_id=proof.execution_id,
            report_id=report.report_id,
            report_hash=report.content_hash,
            manifest_hash=proof.manifest_hash,
            source_count=len(evidence.source_commands),
            publication_epoch=epoch,
            checked_at=after["now"],
            caller_xid=after["xid"],
            caller_pid=after["pid"],
        )
    except RouteEvalReleaseEvidenceRejected:
        raise
    except Exception as exc:
        raise RouteEvalReleaseEvidenceRejected(
            "current Route release evidence required"
        ) from exc


def revalidate_route_eval_proof_signers(
    *,
    scope: TenantScope,
    proof: RouteEvalFinalizationProof,
    manifest_bytes: bytes,
    checked_at: datetime,
    revoked_identity_ids: frozenset[str],
) -> VerifiedRouteEvalProofSigners:
    """Recheck every issuer-signed certificate at one caller-owned clock.

    The revocation set is an input, not established here. Source, Report, Run,
    case bytes, cost and publishable-target authority remain separate gates.
    """
    try:
        if (
            type(scope) is not TenantScope
            or scope.key != ("org-org", "dev-project")
            or type(proof) is not RouteEvalFinalizationProof
            or (proof.tenant.org_id, proof.tenant.project_id) != scope.key
            or type(manifest_bytes) is not bytes
            or hashlib.sha256(manifest_bytes).hexdigest() != proof.manifest_hash
            or type(checked_at) is not datetime
            or checked_at.utcoffset() is None
            or checked_at < proof.finalized_at
            or type(revoked_identity_ids) is not frozenset
            or any(type(identity_id) is not str or not identity_id for identity_id in revoked_identity_ids)
        ):
            raise ValueError
        canonical_route_eval_finalization_proof(proof)
        identities: set[str] = set()
        issuers: set[tuple[str, str]] = set()
        for item in proof.calls:
            signed = item.signed_certificate
            certificate = signed.certificate
            validate_governed_certificate_signature(
                manifest_bytes,
                certificate,
                issuer_input=item.issuer_input,
                signature_base64=signed.signature_base64,
                checked_at=checked_at,
                revoked_identity_ids=revoked_identity_ids,
            )
            identities.add(certificate.identity_id)
            issuers.add((certificate.issuer_id, certificate.issuer_key_id))
        if not identities or not issuers:
            raise ValueError
        return VerifiedRouteEvalProofSigners(
            execution_id=proof.execution_id,
            manifest_hash=proof.manifest_hash,
            identity_ids=tuple(sorted(identities)),
            issuer_keys=tuple(sorted(issuers)),
        )
    except Exception as exc:
        if isinstance(exc, RouteEvalProofAuthorityRejected):
            raise
        raise RouteEvalProofAuthorityRejected(
            "current Route proof signer authority required"
        ) from exc


__all__ = [
    "ISSUER_OWNER",
    "ISSUER_READER",
    "ISSUER_SCHEMA",
    "RouteEvalProofAuthorityRejected",
    "RouteEvalReleaseEvidenceRejected",
    "RouteEvalReleaseEvidence",
    "VerifiedRouteEvalProofAuthority",
    "VerifiedRouteEvalReleaseEvidence",
    "VerifiedRouteEvalProofSigners",
    "install_closed_route_eval_proof_authority",
    "read_current_route_eval_proof_authority",
    "verify_route_eval_release_evidence",
    "revalidate_route_eval_proof_signers",
]

"""Closed immutable Model proof storage, without issuer or execution authority.

Bodies are byte-preserved and hash-bound. Their semantic and cryptographic
validity belongs to a future narrow writer and proof reader, not these tables.
"""

OWNER = 'aos_model_eval_execution_owner'
SCHEMA = 'aos_model_eval_execution_private'
TABLES = ('manifest', 'case_result', 'obligation_event', 'report_link')
ISSUER_OWNER = 'aos_model_eval_issuer_owner'
ISSUER_SCHEMA = 'aos_model_eval_issuer_private'
ISSUER_TABLES = ('issuer_root', 'executor_certificate', 'authority_withdrawal')

ROLE_SQL = f"""
DO $role$ DECLARE r record; BEGIN
 SELECT * INTO r FROM pg_roles WHERE rolname='{OWNER}';
 IF NOT FOUND THEN
  CREATE ROLE {OWNER} NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB
   NOCREATEROLE NOREPLICATION NOBYPASSRLS;
 ELSIF r.rolcanlogin OR r.rolinherit OR r.rolsuper OR r.rolcreatedb
  OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls THEN
  RAISE EXCEPTION 'MODEL_EXECUTION_OWNER_DRIFT' USING ERRCODE='42501';
 END IF;
 IF EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid='{OWNER}'::regrole OR member='{OWNER}'::regrole)
 OR EXISTS(SELECT 1 FROM pg_class WHERE relowner='{OWNER}'::regrole)
 OR EXISTS(SELECT 1 FROM pg_proc WHERE proowner='{OWNER}'::regrole)
 OR EXISTS(SELECT 1 FROM pg_namespace WHERE nspowner='{OWNER}'::regrole)
 OR EXISTS(SELECT 1 FROM pg_database WHERE datdba='{OWNER}'::regrole)
 OR EXISTS(SELECT 1 FROM pg_class c,LATERAL aclexplode(c.relacl) a WHERE a.grantee='{OWNER}'::regrole)
 OR EXISTS(SELECT 1 FROM pg_attribute c,LATERAL aclexplode(c.attacl) a WHERE a.grantee='{OWNER}'::regrole)
 OR EXISTS(SELECT 1 FROM pg_proc p,LATERAL aclexplode(p.proacl) a WHERE a.grantee='{OWNER}'::regrole)
 OR EXISTS(SELECT 1 FROM pg_namespace n,LATERAL aclexplode(n.nspacl) a WHERE a.grantee='{OWNER}'::regrole)
 OR EXISTS(SELECT 1 FROM pg_default_acl WHERE defaclrole='{OWNER}'::regrole)
 OR EXISTS(SELECT 1 FROM pg_default_acl d,LATERAL aclexplode(d.defaclacl) a WHERE a.grantee='{OWNER}'::regrole)
 THEN RAISE EXCEPTION 'MODEL_EXECUTION_OWNER_DRIFT' USING ERRCODE='42501'; END IF;
END $role$;
"""

_SCOPE = """org_id text NOT NULL CHECK(org_id='org-org'),
 project_id text NOT NULL CHECK(project_id='dev-project'),
 execution_id text NOT NULL CHECK(length(execution_id) BETWEEN 1 AND 200 AND execution_id=btrim(execution_id))"""
_BODY = """content_hash text NOT NULL CHECK(content_hash ~ '^[0-9a-f]{64}$'),
 body bytea NOT NULL CHECK(octet_length(body) BETWEEN 1 AND 8388608),
 CHECK(content_hash=encode(pg_catalog.sha256(body),'hex'))"""
_CASE = """case_id text NOT NULL CHECK(length(case_id) BETWEEN 1 AND 200 AND case_id=btrim(case_id)),
 purpose text NOT NULL CHECK(purpose IN ('target','judge')),
 attempt integer NOT NULL CHECK(attempt=1)"""

TABLE_SQL = f"""
CREATE TABLE {SCHEMA}.manifest({_SCOPE},{_BODY},
 PRIMARY KEY(org_id,project_id,execution_id));
CREATE TABLE {SCHEMA}.case_result({_SCOPE},{_CASE},{_BODY},
 PRIMARY KEY(org_id,project_id,execution_id,case_id,purpose,attempt),
 FOREIGN KEY(org_id,project_id,execution_id)
  REFERENCES {SCHEMA}.manifest(org_id,project_id,execution_id));
CREATE TABLE {SCHEMA}.obligation_event({_SCOPE},{_CASE},
 event_id text NOT NULL CHECK(length(event_id) BETWEEN 1 AND 200 AND event_id=btrim(event_id)),
 {_BODY},PRIMARY KEY(org_id,project_id,execution_id,event_id),
 FOREIGN KEY(org_id,project_id,execution_id)
  REFERENCES {SCHEMA}.manifest(org_id,project_id,execution_id));
CREATE TABLE {SCHEMA}.report_link({_SCOPE},{_BODY},
 PRIMARY KEY(org_id,project_id,execution_id),
 FOREIGN KEY(org_id,project_id,execution_id)
  REFERENCES {SCHEMA}.manifest(org_id,project_id,execution_id));
"""


def install_closed_storage(execute):
    """Additive migration only: no rows, public entry, trust root, or login."""
    execute(ROLE_SQL)
    execute(f'CREATE SCHEMA {SCHEMA} AUTHORIZATION {OWNER}')
    execute(f'REVOKE ALL ON SCHEMA {SCHEMA} FROM PUBLIC,aos_runtime,aos_provider_capacity_issuer')
    # Only the fresh Owner's global defaults are changed; existing creator
    # defaults are narrowed to the new schema and every object is revoked too.
    execute(f'ALTER DEFAULT PRIVILEGES FOR ROLE {OWNER} REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC')
    for role in (None, OWNER):
        prefix = f'ALTER DEFAULT PRIVILEGES {"FOR ROLE " + role if role else ""} IN SCHEMA {SCHEMA}'
        for kind, privileges in (('TABLES', 'ALL'), ('SEQUENCES', 'ALL'), ('FUNCTIONS', 'ALL')):
            execute(f'{prefix} REVOKE {privileges} ON {kind} FROM PUBLIC,aos_runtime,aos_provider_capacity_issuer')
    execute(f"""CREATE FUNCTION {SCHEMA}.immutable_proof_row() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $body$ BEGIN
      RAISE EXCEPTION 'MODEL_EXECUTION_PROOF_IMMUTABLE' USING ERRCODE='42501';
      END $body$""")
    execute(f'ALTER FUNCTION {SCHEMA}.immutable_proof_row() OWNER TO {OWNER}')
    execute(f'REVOKE ALL ON FUNCTION {SCHEMA}.immutable_proof_row() FROM PUBLIC,aos_runtime,aos_provider_capacity_issuer')
    execute(TABLE_SQL)
    for table in TABLES:
        relation = f'{SCHEMA}.{table}'
        execute(f'ALTER TABLE {relation} OWNER TO {OWNER}')
        execute(f'REVOKE ALL ON {relation} FROM PUBLIC,aos_runtime,aos_provider_capacity_issuer')
        execute(f'ALTER TABLE {relation} ENABLE ROW LEVEL SECURITY')
        execute(f'ALTER TABLE {relation} FORCE ROW LEVEL SECURITY')
        execute(f"""CREATE POLICY model_proof_scope ON {relation} TO {OWNER}
          USING(org_id=NULLIF(current_setting('aos.org_id',true),'')
            AND project_id=NULLIF(current_setting('aos.project_id',true),''))
          WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'')
            AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
        execute(f'CREATE TRIGGER immutable_model_proof_row BEFORE UPDATE OR DELETE ON {relation} '
                f'FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.immutable_proof_row()')
        execute(f'CREATE TRIGGER immutable_model_proof_truncate BEFORE TRUNCATE ON {relation} '
                f'FOR EACH STATEMENT EXECUTE FUNCTION {SCHEMA}.immutable_proof_row()')


def install_closed_issuer_history(execute):
    """Empty immutable history, not bootstrap, issuance or current-root authority."""
    execute(ROLE_SQL.replace(OWNER, ISSUER_OWNER))
    execute(f'CREATE SCHEMA {ISSUER_SCHEMA} AUTHORIZATION {ISSUER_OWNER}')
    # The new private Issuer can read only the descriptive original manifest.
    execute(f'GRANT USAGE ON SCHEMA {SCHEMA} TO {ISSUER_OWNER}')
    execute(f'GRANT SELECT ON {SCHEMA}.manifest TO {ISSUER_OWNER}')
    execute(f'GRANT SELECT ON {SCHEMA}.case_result TO {ISSUER_OWNER}')
    execute(f"""CREATE POLICY model_issuer_case_read ON {SCHEMA}.case_result
      FOR SELECT TO {ISSUER_OWNER}
      USING(org_id=NULLIF(current_setting('aos.org_id',true),'')
        AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    execute(f"""CREATE POLICY model_issuer_manifest_read ON {SCHEMA}.manifest
      FOR SELECT TO {ISSUER_OWNER}
      USING(org_id=NULLIF(current_setting('aos.org_id',true),'')
        AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    denied = f'PUBLIC,aos_runtime,aos_provider_capacity_issuer,{OWNER}'
    execute(f'REVOKE ALL ON SCHEMA {ISSUER_SCHEMA} FROM {denied}')
    execute(f'ALTER DEFAULT PRIVILEGES FOR ROLE {ISSUER_OWNER} REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC')
    for role in (None, ISSUER_OWNER):
        prefix = f'ALTER DEFAULT PRIVILEGES {"FOR ROLE " + role if role else ""} IN SCHEMA {ISSUER_SCHEMA}'
        for kind in ('TABLES', 'SEQUENCES', 'FUNCTIONS'):
            execute(f'{prefix} REVOKE ALL ON {kind} FROM {denied}')
    execute(f"""CREATE FUNCTION {ISSUER_SCHEMA}.immutable_issuer_history() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $body$ BEGIN
      RAISE EXCEPTION 'MODEL_ISSUER_HISTORY_IMMUTABLE' USING ERRCODE='42501';
      END $body$""")
    execute(f'ALTER FUNCTION {ISSUER_SCHEMA}.immutable_issuer_history() OWNER TO {ISSUER_OWNER}')
    execute(f'REVOKE ALL ON FUNCTION {ISSUER_SCHEMA}.immutable_issuer_history() FROM {denied}')
    scope = """org_id text NOT NULL CHECK(org_id='org-org'),
      project_id text NOT NULL CHECK(project_id='dev-project')"""
    issuer = "issuer_id text NOT NULL CHECK(length(issuer_id) BETWEEN 1 AND 200 AND issuer_id=btrim(issuer_id))"
    key = "key_id text NOT NULL CHECK(length(key_id) BETWEEN 1 AND 200 AND key_id=btrim(key_id))"
    execute(f"""CREATE TABLE {ISSUER_SCHEMA}.issuer_root({scope},{issuer},{key},
      bootstrap_hash text NOT NULL CHECK(bootstrap_hash ~ '^[0-9a-f]{{64}}$'),
      {_BODY},created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,issuer_id,key_id));
      CREATE TABLE {ISSUER_SCHEMA}.executor_certificate({_SCOPE},{_CASE},{issuer},{key},
      {_BODY},created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,content_hash),
      UNIQUE(org_id,project_id,execution_id,case_id,purpose,attempt),
      FOREIGN KEY(org_id,project_id,issuer_id,key_id)
        REFERENCES {ISSUER_SCHEMA}.issuer_root(org_id,project_id,issuer_id,key_id),
      FOREIGN KEY(org_id,project_id,execution_id)
        REFERENCES {SCHEMA}.manifest(org_id,project_id,execution_id));
      CREATE TABLE {ISSUER_SCHEMA}.authority_withdrawal({scope},
      event_id text NOT NULL CHECK(length(event_id) BETWEEN 1 AND 200 AND event_id=btrim(event_id)),
      issuer_id text CHECK(length(issuer_id) BETWEEN 1 AND 200 AND issuer_id=btrim(issuer_id)),
      key_id text CHECK(length(key_id) BETWEEN 1 AND 200 AND key_id=btrim(key_id)),
      certificate_hash text CHECK(certificate_hash ~ '^[0-9a-f]{{64}}$'),
      {_BODY},created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,event_id),
      CHECK((issuer_id IS NOT NULL AND key_id IS NOT NULL AND certificate_hash IS NULL)
        OR (issuer_id IS NULL AND key_id IS NULL AND certificate_hash IS NOT NULL)),
      FOREIGN KEY(org_id,project_id,issuer_id,key_id)
        REFERENCES {ISSUER_SCHEMA}.issuer_root(org_id,project_id,issuer_id,key_id),
      FOREIGN KEY(org_id,project_id,certificate_hash)
        REFERENCES {ISSUER_SCHEMA}.executor_certificate(org_id,project_id,content_hash));
      CREATE UNIQUE INDEX model_issuer_withdraw_once
        ON {ISSUER_SCHEMA}.authority_withdrawal(org_id,project_id,issuer_id,key_id)
        WHERE issuer_id IS NOT NULL;
      CREATE UNIQUE INDEX model_certificate_withdraw_once
        ON {ISSUER_SCHEMA}.authority_withdrawal(org_id,project_id,certificate_hash)
        WHERE certificate_hash IS NOT NULL""")
    for table in ISSUER_TABLES:
        relation = f'{ISSUER_SCHEMA}.{table}'
        execute(f'ALTER TABLE {relation} OWNER TO {ISSUER_OWNER}')
        execute(f'REVOKE ALL ON {relation} FROM {denied}')
        execute(f'ALTER TABLE {relation} ENABLE ROW LEVEL SECURITY')
        execute(f'ALTER TABLE {relation} FORCE ROW LEVEL SECURITY')
        execute(f"""CREATE POLICY model_issuer_scope ON {relation} TO {ISSUER_OWNER}
          USING(org_id=NULLIF(current_setting('aos.org_id',true),'')
            AND project_id=NULLIF(current_setting('aos.project_id',true),''))
          WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'')
            AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
        execute(f'CREATE TRIGGER immutable_model_issuer_row BEFORE UPDATE OR DELETE ON {relation} '
                f'FOR EACH ROW EXECUTE FUNCTION {ISSUER_SCHEMA}.immutable_issuer_history()')
        execute(f'CREATE TRIGGER immutable_model_issuer_truncate BEFORE TRUNCATE ON {relation} '
                f'FOR EACH STATEMENT EXECUTE FUNCTION {ISSUER_SCHEMA}.immutable_issuer_history()')
    # Currentness substrate only. No root is bootstrapped and no reader/writer
    # role receives access; a future formal issuer must validate provenance.
    execute(f"""ALTER TABLE {ISSUER_SCHEMA}.issuer_root ADD UNIQUE
      (org_id,project_id,issuer_id,key_id,content_hash);
      CREATE TABLE {ISSUER_SCHEMA}.issuer_epoch({scope},{issuer},{key},
      epoch bigint NOT NULL CHECK(epoch>=1),
      root_hash text CHECK(root_hash ~ '^[0-9a-f]{{64}}$'),
      updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,issuer_id,key_id),
      FOREIGN KEY(org_id,project_id,issuer_id,key_id)
        REFERENCES {ISSUER_SCHEMA}.issuer_root(org_id,project_id,issuer_id,key_id),
      FOREIGN KEY(org_id,project_id,issuer_id,key_id,root_hash)
        REFERENCES {ISSUER_SCHEMA}.issuer_root(org_id,project_id,issuer_id,key_id,content_hash));
      CREATE FUNCTION {ISSUER_SCHEMA}.issuer_epoch_transition() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $body$ BEGIN
      IF (TG_OP='INSERT' AND (NEW.epoch<>1 OR NEW.root_hash IS NULL))
        OR (TG_OP='UPDATE' AND (
          (NEW.org_id,NEW.project_id,NEW.issuer_id,NEW.key_id)
            IS DISTINCT FROM (OLD.org_id,OLD.project_id,OLD.issuer_id,OLD.key_id)
          OR NEW.epoch<>OLD.epoch+1 OR OLD.root_hash IS NULL OR NEW.root_hash IS NOT NULL))
      THEN RAISE EXCEPTION 'MODEL_ISSUER_EPOCH_TRANSITION' USING ERRCODE='42501'; END IF;
      NEW.updated_at:=clock_timestamp(); RETURN NEW;
      END $body$""")
    execute(f'ALTER FUNCTION {ISSUER_SCHEMA}.issuer_epoch_transition() OWNER TO {ISSUER_OWNER}')
    execute(f'REVOKE ALL ON FUNCTION {ISSUER_SCHEMA}.issuer_epoch_transition() FROM {denied}')
    relation = f'{ISSUER_SCHEMA}.issuer_epoch'
    execute(f'ALTER TABLE {relation} OWNER TO {ISSUER_OWNER}')
    execute(f'REVOKE ALL ON {relation} FROM {denied}')
    execute(f'ALTER TABLE {relation} ENABLE ROW LEVEL SECURITY')
    execute(f'ALTER TABLE {relation} FORCE ROW LEVEL SECURITY')
    execute(f"""CREATE POLICY model_issuer_epoch_scope ON {relation} TO {ISSUER_OWNER}
      USING(org_id=NULLIF(current_setting('aos.org_id',true),'')
        AND project_id=NULLIF(current_setting('aos.project_id',true),''))
      WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'')
        AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    execute(f'CREATE TRIGGER model_issuer_epoch_transition BEFORE INSERT OR UPDATE ON {relation} '
            f'FOR EACH ROW EXECUTE FUNCTION {ISSUER_SCHEMA}.issuer_epoch_transition()')
    execute(f'CREATE TRIGGER immutable_model_issuer_epoch_delete BEFORE DELETE ON {relation} '
            f'FOR EACH ROW EXECUTE FUNCTION {ISSUER_SCHEMA}.immutable_issuer_history()')
    execute(f'CREATE TRIGGER immutable_model_issuer_epoch_truncate BEFORE TRUNCATE ON {relation} '
            f'FOR EACH STATEMENT EXECUTE FUNCTION {ISSUER_SCHEMA}.immutable_issuer_history()')
    execute(f"""CREATE FUNCTION {ISSUER_SCHEMA}.advance_root_withdrawal_epoch() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $body$ BEGIN
      IF NEW.issuer_id IS NOT NULL THEN
        UPDATE {ISSUER_SCHEMA}.issuer_epoch SET epoch=epoch+1,root_hash=NULL
          WHERE org_id=NEW.org_id AND project_id=NEW.project_id
            AND issuer_id=NEW.issuer_id AND key_id=NEW.key_id AND root_hash IS NOT NULL;
        IF NOT FOUND THEN
          RAISE EXCEPTION 'MODEL_ISSUER_WITHDRAWAL_CURRENT_HEAD_MISSING' USING ERRCODE='42501';
        END IF;
      ELSE
        PERFORM 1 FROM {ISSUER_SCHEMA}.issuer_epoch h
          JOIN {ISSUER_SCHEMA}.executor_certificate c
            ON (h.org_id,h.project_id,h.issuer_id,h.key_id)
              =(c.org_id,c.project_id,c.issuer_id,c.key_id)
          WHERE c.org_id=NEW.org_id AND c.project_id=NEW.project_id
            AND c.content_hash=NEW.certificate_hash FOR SHARE OF h;
        IF NOT FOUND THEN
          RAISE EXCEPTION 'MODEL_CERTIFICATE_ROOT_HEAD_MISSING' USING ERRCODE='42501';
        END IF;
        UPDATE {ISSUER_SCHEMA}.certificate_epoch SET epoch=epoch+1,active_hash=NULL
          WHERE org_id=NEW.org_id AND project_id=NEW.project_id
            AND certificate_hash=NEW.certificate_hash AND active_hash IS NOT NULL;
        IF NOT FOUND THEN
          RAISE EXCEPTION 'MODEL_CERTIFICATE_WITHDRAWAL_CURRENT_HEAD_MISSING' USING ERRCODE='42501';
        END IF;
      END IF;
      RETURN NULL;
      END $body$""")
    execute(f'ALTER FUNCTION {ISSUER_SCHEMA}.advance_root_withdrawal_epoch() OWNER TO {ISSUER_OWNER}')
    execute(f'REVOKE ALL ON FUNCTION {ISSUER_SCHEMA}.advance_root_withdrawal_epoch() FROM {denied}')
    execute(f'CREATE TRIGGER advance_model_root_withdrawal_epoch AFTER INSERT '
            f'ON {ISSUER_SCHEMA}.authority_withdrawal FOR EACH ROW '
            f'EXECUTE FUNCTION {ISSUER_SCHEMA}.advance_root_withdrawal_epoch()')


def install_closed_certificate_epochs(execute):
    """Add currentness to closed certificate history, without issuance rights."""
    denied=f'PUBLIC,aos_runtime,aos_provider_capacity_issuer,{OWNER}'
    execute(f"""CREATE TABLE {ISSUER_SCHEMA}.certificate_epoch(
      org_id text NOT NULL CHECK(org_id='org-org'),
      project_id text NOT NULL CHECK(project_id='dev-project'),
      certificate_hash text NOT NULL CHECK(certificate_hash ~ '^[0-9a-f]{{64}}$'),
      epoch bigint NOT NULL CHECK(epoch>=1),
      active_hash text CHECK(active_hash=certificate_hash),
      updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,certificate_hash),
      FOREIGN KEY(org_id,project_id,certificate_hash)
        REFERENCES {ISSUER_SCHEMA}.executor_certificate(org_id,project_id,content_hash));
      CREATE FUNCTION {ISSUER_SCHEMA}.certificate_epoch_transition() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $body$ BEGIN
      IF (TG_OP='INSERT' AND (NEW.epoch<>1 OR NEW.active_hash IS NULL
          OR NEW.active_hash<>NEW.certificate_hash))
        OR (TG_OP='UPDATE' AND (
          (NEW.org_id,NEW.project_id,NEW.certificate_hash)
            IS DISTINCT FROM (OLD.org_id,OLD.project_id,OLD.certificate_hash)
          OR NEW.epoch<>OLD.epoch+1 OR OLD.active_hash IS NULL OR NEW.active_hash IS NOT NULL))
      THEN RAISE EXCEPTION 'MODEL_CERTIFICATE_EPOCH_TRANSITION' USING ERRCODE='42501'; END IF;
      NEW.updated_at:=clock_timestamp(); RETURN NEW;
      END $body$;
      CREATE FUNCTION {ISSUER_SCHEMA}.initialize_certificate_epoch() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $body$ BEGIN
      PERFORM 1 FROM {ISSUER_SCHEMA}.issuer_epoch
        WHERE org_id=NEW.org_id AND project_id=NEW.project_id
          AND issuer_id=NEW.issuer_id AND key_id=NEW.key_id AND root_hash IS NOT NULL FOR SHARE;
      IF NOT FOUND THEN
        RAISE EXCEPTION 'MODEL_CERTIFICATE_ACTIVE_ROOT_HEAD_MISSING' USING ERRCODE='42501';
      END IF;
      INSERT INTO {ISSUER_SCHEMA}.certificate_epoch(org_id,project_id,certificate_hash,epoch,active_hash)
        VALUES(NEW.org_id,NEW.project_id,NEW.content_hash,1,NEW.content_hash);
      RETURN NULL;
      END $body$""")
    for name in ('certificate_epoch_transition','initialize_certificate_epoch'):
        execute(f'ALTER FUNCTION {ISSUER_SCHEMA}.{name}() OWNER TO {ISSUER_OWNER}')
        execute(f'REVOKE ALL ON FUNCTION {ISSUER_SCHEMA}.{name}() FROM {denied}')
    relation=f'{ISSUER_SCHEMA}.certificate_epoch'
    execute(f'ALTER TABLE {relation} OWNER TO {ISSUER_OWNER}')
    execute(f'REVOKE ALL ON {relation} FROM {denied}')
    execute(f'ALTER TABLE {relation} ENABLE ROW LEVEL SECURITY')
    execute(f'ALTER TABLE {relation} FORCE ROW LEVEL SECURITY')
    execute(f"""CREATE POLICY model_certificate_epoch_scope ON {relation} TO {ISSUER_OWNER}
      USING(org_id=NULLIF(current_setting('aos.org_id',true),'')
        AND project_id=NULLIF(current_setting('aos.project_id',true),''))
      WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'')
        AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    execute(f'CREATE TRIGGER model_certificate_epoch_transition BEFORE INSERT OR UPDATE ON {relation} '
            f'FOR EACH ROW EXECUTE FUNCTION {ISSUER_SCHEMA}.certificate_epoch_transition()')
    execute(f'CREATE TRIGGER immutable_model_certificate_epoch_delete BEFORE DELETE ON {relation} '
            f'FOR EACH ROW EXECUTE FUNCTION {ISSUER_SCHEMA}.immutable_issuer_history()')
    execute(f'CREATE TRIGGER immutable_model_certificate_epoch_truncate BEFORE TRUNCATE ON {relation} '
            f'FOR EACH STATEMENT EXECUTE FUNCTION {ISSUER_SCHEMA}.immutable_issuer_history()')
    execute(f'CREATE TRIGGER initialize_model_certificate_epoch AFTER INSERT '
            f'ON {ISSUER_SCHEMA}.executor_certificate FOR EACH ROW '
            f'EXECUTE FUNCTION {ISSUER_SCHEMA}.initialize_certificate_epoch()')


def install_closed_model_identity_authority(execute):
    """Explicit isolated artifact: same-domain binding, never formal identity trust.

    No legacy backfill, migration activation, runtime grants or public entry.
    The narrow Python writer verifies original signed bytes before registration;
    triggers derive binding fields again from the stored certificate body.
    """
    s = ISSUER_SCHEMA
    denied = f'PUBLIC,aos_runtime,aos_provider_capacity_issuer,{OWNER}'
    scope = "org_id text NOT NULL CHECK(org_id='org-org'),project_id text NOT NULL CHECK(project_id='dev-project')"
    identity = "identity_id text NOT NULL CHECK(length(identity_id) BETWEEN 1 AND 200 AND identity_id=btrim(identity_id))"
    execute(f"""CREATE TABLE {s}.identity_epoch({scope},{identity},
      purpose text NOT NULL CHECK(purpose IN ('target','judge')),
      key_hash text NOT NULL CHECK(key_hash ~ '^[0-9a-f]{{64}}$'),
      epoch bigint NOT NULL CHECK(epoch>=1), version bigint NOT NULL CHECK(version>=1),
      active boolean NOT NULL, updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,identity_id),
      UNIQUE(org_id,project_id,identity_id,purpose,key_hash));
      CREATE TABLE {s}.certificate_identity_binding({scope},
      certificate_hash text NOT NULL CHECK(certificate_hash ~ '^[0-9a-f]{{64}}$'),
      {identity},purpose text NOT NULL,key_hash text NOT NULL,
      PRIMARY KEY(org_id,project_id,certificate_hash),
      FOREIGN KEY(org_id,project_id,certificate_hash)
        REFERENCES {s}.executor_certificate(org_id,project_id,content_hash),
      FOREIGN KEY(org_id,project_id,identity_id,purpose,key_hash)
        REFERENCES {s}.identity_epoch(org_id,project_id,identity_id,purpose,key_hash));
      CREATE TABLE {s}.identity_withdrawal({scope},
      event_id text NOT NULL CHECK(length(event_id) BETWEEN 1 AND 200 AND event_id=btrim(event_id)),
      {identity},{_BODY},created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,event_id),UNIQUE(org_id,project_id,identity_id),
      FOREIGN KEY(org_id,project_id,identity_id)
        REFERENCES {s}.identity_epoch(org_id,project_id,identity_id));
      CREATE FUNCTION {s}.identity_epoch_transition() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $f$ BEGIN
        IF pg_trigger_depth()<2 OR
          (TG_OP='INSERT' AND (NEW.epoch<>1 OR NEW.version<>1 OR NOT NEW.active)) OR
          (TG_OP='UPDATE' AND (
            (NEW.org_id,NEW.project_id,NEW.identity_id,NEW.purpose,NEW.key_hash)
              IS DISTINCT FROM (OLD.org_id,OLD.project_id,OLD.identity_id,OLD.purpose,OLD.key_hash)
            OR NOT OLD.active OR NEW.version<>OLD.version+1
            OR (NEW.active AND NEW.epoch<>OLD.epoch)
            OR (NOT NEW.active AND NEW.epoch<>OLD.epoch+1)))
        THEN RAISE EXCEPTION 'MODEL_IDENTITY_EPOCH_TRANSITION' USING ERRCODE='42501'; END IF;
        NEW.updated_at:=clock_timestamp();RETURN NEW;
      END $f$;
      CREATE FUNCTION {s}.derive_certificate_identity() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $f$
      DECLARE c record; j jsonb; BEGIN
        SELECT h.root_hash INTO c FROM {s}.issuer_epoch h
          JOIN {s}.executor_certificate x ON
          (h.org_id,h.project_id,h.issuer_id,h.key_id)=(x.org_id,x.project_id,x.issuer_id,x.key_id)
          WHERE x.org_id=NEW.org_id AND x.project_id=NEW.project_id
            AND x.content_hash=NEW.certificate_hash FOR SHARE OF h;
        IF NOT FOUND OR c.root_hash IS NULL THEN
          RAISE EXCEPTION 'MODEL_IDENTITY_ROOT_INACTIVE' USING ERRCODE='42501'; END IF;
        SELECT x.*,h.active_hash INTO c FROM {s}.executor_certificate x
          JOIN {s}.certificate_epoch h ON
          (h.org_id,h.project_id,h.certificate_hash)=(x.org_id,x.project_id,x.content_hash)
          WHERE x.org_id=NEW.org_id AND x.project_id=NEW.project_id
            AND x.content_hash=NEW.certificate_hash FOR SHARE OF h;
        IF NOT FOUND OR c.active_hash IS NULL THEN
          RAISE EXCEPTION 'MODEL_IDENTITY_CERTIFICATE_INACTIVE' USING ERRCODE='42501'; END IF;
        j:=convert_from(c.body,'UTF8')::jsonb;
        IF j->>'schemaVersion' IS DISTINCT FROM 'aos.model-eval-signed-certificate-envelope/v1'
          OR j#>>'{{certificate,tenant,orgId}}' IS DISTINCT FROM NEW.org_id
          OR j#>>'{{certificate,tenant,projectId}}' IS DISTINCT FROM NEW.project_id
          OR j#>>'{{certificate,executionId}}' IS DISTINCT FROM c.execution_id
          OR j#>>'{{certificate,caseId}}' IS DISTINCT FROM c.case_id
          OR j#>>'{{certificate,purpose}}' IS DISTINCT FROM c.purpose
          OR j#>>'{{certificate,issuerId}}' IS DISTINCT FROM c.issuer_id
          OR j#>>'{{certificate,issuerKeyId}}' IS DISTINCT FROM c.key_id
          OR j#>>'{{certificate,leg,identityKeyHash}}' IS DISTINCT FROM
             encode(sha256(decode(j#>>'{{certificate,publicKeyBase64}}','base64')),'hex')
        THEN RAISE EXCEPTION 'MODEL_IDENTITY_CERTIFICATE_BINDING' USING ERRCODE='42501'; END IF;
        NEW.identity_id:=j#>>'{{certificate,leg,identityId}}';
        NEW.purpose:=c.purpose;NEW.key_hash:=j#>>'{{certificate,leg,identityKeyHash}}';
        INSERT INTO {s}.identity_epoch(org_id,project_id,identity_id,purpose,key_hash,epoch,version,active)
          VALUES(NEW.org_id,NEW.project_id,NEW.identity_id,NEW.purpose,NEW.key_hash,1,1,true)
          ON CONFLICT(org_id,project_id,identity_id) DO UPDATE SET version=identity_epoch.version+1
          WHERE identity_epoch.active AND identity_epoch.purpose=EXCLUDED.purpose
            AND identity_epoch.key_hash=EXCLUDED.key_hash;
        IF NOT FOUND THEN RAISE EXCEPTION 'MODEL_IDENTITY_BOUND_OR_REVOKED' USING ERRCODE='42501'; END IF;
        RETURN NEW;
      END $f$;
      CREATE FUNCTION {s}.advance_identity_withdrawal() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $f$ DECLARE j jsonb; BEGIN
        j:=convert_from(NEW.body,'UTF8')::jsonb;
        IF j IS DISTINCT FROM jsonb_build_object('schemaVersion','aos.model-eval-identity-withdrawal/v1',
          'tenant',jsonb_build_object('orgId',NEW.org_id,'projectId',NEW.project_id),
          'identityId',NEW.identity_id,'eventId',NEW.event_id)
        THEN RAISE EXCEPTION 'MODEL_IDENTITY_WITHDRAWAL_BODY' USING ERRCODE='42501'; END IF;
        UPDATE {s}.identity_epoch SET epoch=epoch+1,version=version+1,active=false
          WHERE org_id=NEW.org_id AND project_id=NEW.project_id AND identity_id=NEW.identity_id AND active;
        IF NOT FOUND THEN RAISE EXCEPTION 'MODEL_IDENTITY_WITHDRAWAL_HEAD' USING ERRCODE='42501'; END IF;
        NEW.created_at:=clock_timestamp();RETURN NEW;
      END $f$""")
    for name in ('identity_epoch_transition','derive_certificate_identity','advance_identity_withdrawal'):
        execute(f'ALTER FUNCTION {s}.{name}() OWNER TO {ISSUER_OWNER}')
        execute(f'REVOKE ALL ON FUNCTION {s}.{name}() FROM {denied}')
    for table in ('identity_epoch','certificate_identity_binding','identity_withdrawal'):
        relation=f'{s}.{table}'
        execute(f'ALTER TABLE {relation} OWNER TO {ISSUER_OWNER}')
        execute(f'REVOKE ALL ON {relation} FROM {denied}')
        execute(f'ALTER TABLE {relation} ENABLE ROW LEVEL SECURITY')
        execute(f'ALTER TABLE {relation} FORCE ROW LEVEL SECURITY')
        execute(f"""CREATE POLICY model_identity_scope ON {relation} TO {ISSUER_OWNER}
          USING(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
          WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
        mutations='DELETE' if table=='identity_epoch' else 'UPDATE OR DELETE'
        execute(f'CREATE TRIGGER immutable_identity_row BEFORE {mutations} ON {relation} FOR EACH ROW EXECUTE FUNCTION {s}.immutable_issuer_history()')
        execute(f'CREATE TRIGGER immutable_identity_truncate BEFORE TRUNCATE ON {relation} FOR EACH STATEMENT EXECUTE FUNCTION {s}.immutable_issuer_history()')
    execute(f'CREATE TRIGGER identity_epoch_transition BEFORE INSERT OR UPDATE ON {s}.identity_epoch FOR EACH ROW EXECUTE FUNCTION {s}.identity_epoch_transition()')
    execute(f'CREATE TRIGGER derive_certificate_identity BEFORE INSERT ON {s}.certificate_identity_binding FOR EACH ROW EXECUTE FUNCTION {s}.derive_certificate_identity()')
    execute(f'CREATE TRIGGER advance_identity_withdrawal BEFORE INSERT ON {s}.identity_withdrawal FOR EACH ROW EXECUTE FUNCTION {s}.advance_identity_withdrawal()')


RUNTIME_EXECUTOR_FACT = 'public.read_model_executor_set_facts(text,text)'


def runtime_executor_fact_statements():
    """Explicit isolated read bridge. No installation, root trust or admission."""
    s=ISSUER_SCHEMA
    return (
        f'''CREATE FUNCTION public.read_model_executor_set_facts(p_execution text,p_hash text)
        RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $fact$
        DECLARE p record; r record; h record; packed jsonb; BEGIN
          IF current_setting('role',true) IS DISTINCT FROM 'aos_runtime'
            OR current_setting('transaction_isolation') IS DISTINCT FROM 'serializable'
            OR current_setting('aos.org_id',true) IS DISTINCT FROM 'org-org'
            OR current_setting('aos.project_id',true) IS DISTINCT FROM 'dev-project'
            OR p_execution IS NULL OR length(p_execution) NOT BETWEEN 1 AND 200
            OR p_execution IS DISTINCT FROM btrim(p_execution)
            OR p_hash IS NULL OR p_hash !~ '^[0-9a-f]{{64}}$' THEN
            RAISE EXCEPTION 'MODEL_EXECUTOR_FACT_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
          SELECT * INTO p FROM {SCHEMA}.manifest WHERE org_id='org-org' AND project_id='dev-project'
            AND execution_id=p_execution AND content_hash=p_hash;
          IF NOT FOUND THEN RAISE EXCEPTION 'MODEL_EXECUTOR_FACT_MANIFEST_REQUIRED' USING ERRCODE='23514'; END IF;
          FOR r IN SELECT DISTINCT issuer_id,key_id FROM {s}.executor_certificate
            WHERE org_id='org-org' AND project_id='dev-project' AND execution_id=p_execution ORDER BY issuer_id,key_id LOOP
            SELECT e.epoch,e.root_hash,x.content_hash INTO h FROM {s}.issuer_epoch e
              JOIN {s}.issuer_root x USING(org_id,project_id,issuer_id,key_id)
              WHERE e.org_id='org-org' AND e.project_id='dev-project' AND e.issuer_id=r.issuer_id AND e.key_id=r.key_id FOR SHARE OF e;
            IF NOT FOUND OR h.root_hash IS NULL OR h.root_hash IS DISTINCT FROM h.content_hash THEN
              RAISE EXCEPTION 'MODEL_EXECUTOR_FACT_ROOT_REQUIRED' USING ERRCODE='23514'; END IF;
          END LOOP;
          FOR r IN SELECT content_hash FROM {s}.executor_certificate WHERE org_id='org-org'
            AND project_id='dev-project' AND execution_id=p_execution ORDER BY content_hash LOOP
            SELECT epoch,active_hash INTO h FROM {s}.certificate_epoch WHERE org_id='org-org'
              AND project_id='dev-project' AND certificate_hash=r.content_hash FOR SHARE;
            IF NOT FOUND OR h.active_hash IS DISTINCT FROM r.content_hash THEN
              RAISE EXCEPTION 'MODEL_EXECUTOR_FACT_CERTIFICATE_REQUIRED' USING ERRCODE='23514'; END IF;
          END LOOP;
          FOR r IN SELECT x.content_hash,b.identity_id,b.purpose,b.key_hash FROM {s}.executor_certificate x
            LEFT JOIN {s}.certificate_identity_binding b ON
              (x.org_id,x.project_id,x.content_hash)=(b.org_id,b.project_id,b.certificate_hash)
            WHERE x.org_id='org-org' AND x.project_id='dev-project' AND x.execution_id=p_execution
            ORDER BY b.identity_id,x.content_hash LOOP
            SELECT epoch,active,purpose,key_hash INTO h FROM {s}.identity_epoch WHERE org_id='org-org'
              AND project_id='dev-project' AND identity_id=r.identity_id FOR SHARE;
            IF NOT FOUND OR NOT h.active OR h.purpose IS DISTINCT FROM r.purpose OR h.key_hash IS DISTINCT FROM r.key_hash THEN
              RAISE EXCEPTION 'MODEL_EXECUTOR_FACT_IDENTITY_REQUIRED' USING ERRCODE='23514'; END IF;
          END LOOP;
          SELECT jsonb_agg(jsonb_build_object(
            'certificateHash',x.content_hash,'certificateBody',replace(encode(x.body,'base64'),E'\n',''),
            'caseId',x.case_id,'purpose',x.purpose,'attempt',x.attempt,'issuerId',x.issuer_id,'issuerKeyId',x.key_id,
            'rootHash',root.content_hash,'rootBody',replace(encode(root.body,'base64'),E'\n',''),
            'rootEpoch',re.epoch,'certificateEpoch',ce.epoch,'identityEpoch',i.epoch,
            'identityId',i.identity_id,'identityPurpose',i.purpose,'identityKeyHash',i.key_hash,'identityActive',i.active)
            ORDER BY x.content_hash) INTO packed FROM {s}.executor_certificate x
            JOIN {s}.issuer_root root USING(org_id,project_id,issuer_id,key_id)
            JOIN {s}.issuer_epoch re USING(org_id,project_id,issuer_id,key_id)
            JOIN {s}.certificate_epoch ce ON (x.org_id,x.project_id,x.content_hash)=(ce.org_id,ce.project_id,ce.certificate_hash)
            JOIN {s}.certificate_identity_binding b ON (x.org_id,x.project_id,x.content_hash)=(b.org_id,b.project_id,b.certificate_hash)
            JOIN {s}.identity_epoch i ON (b.org_id,b.project_id,b.identity_id,b.purpose,b.key_hash)=
              (i.org_id,i.project_id,i.identity_id,i.purpose,i.key_hash)
            WHERE x.org_id='org-org' AND x.project_id='dev-project' AND x.execution_id=p_execution;
          RETURN jsonb_build_object('manifestHash',p.content_hash,'manifestBody',replace(encode(p.body,'base64'),E'\n',''),
            'certificates',COALESCE(packed,'[]'::jsonb),'callerXid',pg_current_xact_id()::text,
            'callerPid',pg_backend_pid(),'checkedAt',clock_timestamp(),'executionAllowed',false);
        END $fact$''',
        f'ALTER FUNCTION {RUNTIME_EXECUTOR_FACT} OWNER TO {ISSUER_OWNER}',
        f'REVOKE ALL ON FUNCTION {RUNTIME_EXECUTOR_FACT} FROM PUBLIC',
        f'GRANT EXECUTE ON FUNCTION {RUNTIME_EXECUTOR_FACT} TO aos_runtime',
    )


RUNTIME_TARGET_FACT='public.read_model_target_result_facts(text,text,text)'


def runtime_target_fact_statements():
    """Explicit read-only Target artifact; never installs or authorizes calls."""
    return (
        f'''CREATE FUNCTION public.read_model_target_result_facts(p_execution text,p_hash text,p_case text)
        RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $target$
        DECLARE executors jsonb; result record; BEGIN
          IF p_case IS NULL OR length(p_case) NOT BETWEEN 1 AND 200 OR p_case IS DISTINCT FROM btrim(p_case) THEN
            RAISE EXCEPTION 'MODEL_TARGET_FACT_CASE_REQUIRED' USING ERRCODE='23514'; END IF;
          executors:=public.read_model_executor_set_facts(p_execution,p_hash);
          SELECT x.body,x.content_hash,cert.created_at AS certificate_created_at,origin.origin_xid INTO result
            FROM {SCHEMA}.case_result x JOIN {ISSUER_SCHEMA}.executor_certificate cert
              USING(org_id,project_id,execution_id,case_id,purpose,attempt)
            LEFT JOIN {ISSUER_SCHEMA}.target_result_origin origin ON
              (x.org_id,x.project_id,x.execution_id,x.case_id,x.purpose,x.attempt,x.content_hash)=
              (origin.org_id,origin.project_id,origin.execution_id,origin.case_id,origin.purpose,origin.attempt,origin.content_hash)
            WHERE x.org_id='org-org' AND x.project_id='dev-project' AND x.execution_id=p_execution
              AND x.case_id=p_case AND x.purpose='target' AND x.attempt=1;
          IF NOT FOUND THEN RAISE EXCEPTION 'MODEL_TARGET_FACT_RESULT_REQUIRED' USING ERRCODE='23514'; END IF;
          IF result.origin_xid IS NULL OR pg_xact_status(result.origin_xid) IS DISTINCT FROM 'committed' THEN
            RAISE EXCEPTION 'MODEL_TARGET_ORIGIN_COMMIT_REQUIRED' USING ERRCODE='23514'; END IF;
          RETURN jsonb_build_object('producerXid',result.origin_xid::text,'producerStatus',pg_xact_status(result.origin_xid),
            'targetHash',result.content_hash,
            'targetBody',replace(encode(result.body,'base64'),E'\n',''),
            'certificateCreatedAt',result.certificate_created_at,
            'callerXid',pg_current_xact_id()::text,'callerPid',pg_backend_pid(),'executionAllowed',false);
        END $target$''',
        f'ALTER FUNCTION {RUNTIME_TARGET_FACT} OWNER TO {ISSUER_OWNER}',
        f'REVOKE ALL ON FUNCTION {RUNTIME_TARGET_FACT} FROM PUBLIC',
        f'GRANT EXECUTE ON FUNCTION {RUNTIME_TARGET_FACT} TO aos_runtime',
    )



def target_origin_statements():
    """Explicit isolated insertion-time provenance, no legacy backfill or admission."""
    table=f'{ISSUER_SCHEMA}.target_result_origin'
    return (
        f'''CREATE TABLE {table}({_SCOPE},{_CASE},content_hash text NOT NULL CHECK(content_hash ~ '^[0-9a-f]{{64}}$'),
          origin_xid xid8 NOT NULL,origin_pid integer NOT NULL CHECK(origin_pid>0),
          CHECK(purpose='target'),PRIMARY KEY(org_id,project_id,execution_id,case_id,purpose,attempt))''',
        f'ALTER TABLE {table} OWNER TO {ISSUER_OWNER}',
        f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY',
        f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY',
        f'''CREATE POLICY target_origin_scope ON {table} TO {ISSUER_OWNER}
          USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
          WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))''',
        f'REVOKE ALL ON {table} FROM PUBLIC,aos_runtime,{OWNER}',
        f'''CREATE FUNCTION {ISSUER_SCHEMA}.guard_target_origin() RETURNS trigger
          LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $guardorigin$
          BEGIN
            IF TG_OP<>'INSERT' OR pg_trigger_depth()<>2 OR NEW.origin_xid IS DISTINCT FROM pg_current_xact_id()
              OR NEW.origin_pid IS DISTINCT FROM pg_backend_pid()
              OR NOT EXISTS(SELECT 1 FROM {SCHEMA}.case_result x WHERE
                (x.org_id,x.project_id,x.execution_id,x.case_id,x.purpose,x.attempt,x.content_hash)=
                (NEW.org_id,NEW.project_id,NEW.execution_id,NEW.case_id,NEW.purpose,NEW.attempt,NEW.content_hash)) THEN
              RAISE EXCEPTION 'MODEL_TARGET_ORIGIN_CAPTURE_ONLY' USING ERRCODE='23514'; END IF;
            RETURN NEW;
          END $guardorigin$''',
        f'ALTER FUNCTION {ISSUER_SCHEMA}.guard_target_origin() OWNER TO {ISSUER_OWNER}',
        f'REVOKE ALL ON FUNCTION {ISSUER_SCHEMA}.guard_target_origin() FROM PUBLIC,aos_runtime,{OWNER}',
        f'CREATE TRIGGER target_origin_insert_guard BEFORE INSERT ON {table} FOR EACH ROW EXECUTE FUNCTION {ISSUER_SCHEMA}.guard_target_origin()',
        f'CREATE TRIGGER target_origin_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION {ISSUER_SCHEMA}.guard_target_origin()',
        f'CREATE TRIGGER target_origin_no_truncate BEFORE TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION {ISSUER_SCHEMA}.guard_target_origin()',
        f'''CREATE FUNCTION {ISSUER_SCHEMA}.capture_target_origin() RETURNS trigger
          LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $captureorigin$
          BEGIN
            IF NEW.purpose='target' THEN
              IF current_setting('role',true) IS DISTINCT FROM '{OWNER}'
                OR current_setting('transaction_isolation') IS DISTINCT FROM 'serializable'
                OR current_setting('aos.org_id',true) IS DISTINCT FROM 'org-org'
                OR current_setting('aos.project_id',true) IS DISTINCT FROM 'dev-project' THEN
                RAISE EXCEPTION 'MODEL_TARGET_ORIGIN_WRITER_REQUIRED' USING ERRCODE='42501'; END IF;
              INSERT INTO {table}(org_id,project_id,execution_id,case_id,purpose,attempt,content_hash,origin_xid,origin_pid)
                VALUES(NEW.org_id,NEW.project_id,NEW.execution_id,NEW.case_id,NEW.purpose,NEW.attempt,
                  NEW.content_hash,pg_current_xact_id(),pg_backend_pid());
            END IF;
            RETURN NEW;
          END $captureorigin$''',
        f'ALTER FUNCTION {ISSUER_SCHEMA}.capture_target_origin() OWNER TO {ISSUER_OWNER}',
        f'REVOKE ALL ON FUNCTION {ISSUER_SCHEMA}.capture_target_origin() FROM PUBLIC,aos_runtime,{OWNER}',
        f'CREATE TRIGGER capture_model_target_origin AFTER INSERT ON {SCHEMA}.case_result FOR EACH ROW EXECUTE FUNCTION {ISSUER_SCHEMA}.capture_target_origin()',
    )

"""Private registry foundation; no trusted initialization or public writer yet.

Empty structures and syntax helpers confer no root trust, Source permission,
or execution right. Anchored registration/currentness is a separate gate.
"""
from aos_api.aip_provider_capacity_publication_store import (
    CAPACITY_ROOT_IDENTIFIER_PROFILE_SQL, CAPACITY_ROOT_SNAPSHOT_PROFILE_SQL,
)

OWNER = 'aos_capacity_publication_owner'
PUBLISHER = 'aos_provider_capacity_policy_publisher'
SCHEMA = 'aos_capacity_publication_private'
TABLES = ('deployment_anchor', 'root_snapshot', 'origin', 'root_entry', 'registry_epoch')


def reserved_role_sql(role):
    if role not in (OWNER, PUBLISHER):
        raise ValueError('reserved publication role required')
    return f"""DO $role$ DECLARE r record; BEGIN
      SELECT * INTO r FROM pg_roles WHERE rolname='{role}';
      IF NOT FOUND THEN
        CREATE ROLE {role} NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
      ELSIF r.rolcanlogin OR r.rolinherit OR r.rolsuper OR r.rolcreatedb OR r.rolcreaterole
          OR r.rolreplication OR r.rolbypassrls THEN
        RAISE EXCEPTION 'CAPACITY_PUBLICATION_RESERVED_ROLE_DRIFT' USING ERRCODE='42501';
      END IF;
      IF EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid='{role}'::regrole OR member='{role}'::regrole)
        OR EXISTS(SELECT 1 FROM pg_class WHERE relowner='{role}'::regrole)
        OR EXISTS(SELECT 1 FROM pg_proc WHERE proowner='{role}'::regrole)
        OR EXISTS(SELECT 1 FROM pg_namespace WHERE nspowner='{role}'::regrole)
        OR EXISTS(SELECT 1 FROM pg_database WHERE datdba='{role}'::regrole)
        OR EXISTS(SELECT 1 FROM pg_class c,LATERAL aclexplode(c.relacl) a WHERE a.grantee='{role}'::regrole)
        OR EXISTS(SELECT 1 FROM pg_attribute c,LATERAL aclexplode(c.attacl) a WHERE a.grantee='{role}'::regrole)
        OR EXISTS(SELECT 1 FROM pg_proc p,LATERAL aclexplode(p.proacl) a WHERE a.grantee='{role}'::regrole)
        OR EXISTS(SELECT 1 FROM pg_namespace n,LATERAL aclexplode(n.nspacl) a WHERE a.grantee='{role}'::regrole)
        OR EXISTS(SELECT 1 FROM pg_default_acl d WHERE d.defaclrole='{role}'::regrole)
        OR EXISTS(SELECT 1 FROM pg_default_acl d,LATERAL aclexplode(d.defaclacl) a WHERE a.grantee='{role}'::regrole) THEN
        RAISE EXCEPTION 'CAPACITY_PUBLICATION_RESERVED_ROLE_DRIFT' USING ERRCODE='42501';
      END IF;
    END $role$;"""


TABLE_SQL = r"""
CREATE TABLE aos_capacity_publication_private.deployment_anchor(
 org_id text NOT NULL CHECK(org_id='org-org'),project_id text NOT NULL CHECK(project_id='dev-project'),
 anchor_revision text NOT NULL CHECK(anchor_revision ~ '^sha256:[0-9a-f]{64}$'),
 signer_publisher text NOT NULL CHECK(length(signer_publisher) BETWEEN 1 AND 200 AND signer_publisher=btrim(signer_publisher)),
 signer_key_id text NOT NULL CHECK(length(signer_key_id) BETWEEN 1 AND 200 AND signer_key_id=btrim(signer_key_id)),
 signer_public_key bytea NOT NULL CHECK(octet_length(signer_public_key)=32),
 publisher_subject text NOT NULL CHECK(length(publisher_subject) BETWEEN 1 AND 200 AND publisher_subject=btrim(publisher_subject)),
 deployment_target jsonb NOT NULL CHECK(jsonb_typeof(deployment_target)='object'),
 PRIMARY KEY(org_id,project_id,anchor_revision));
CREATE TABLE aos_capacity_publication_private.root_snapshot(
 org_id text NOT NULL CHECK(org_id='org-org'),project_id text NOT NULL CHECK(project_id='dev-project'),
 snapshot_hash text NOT NULL CHECK(snapshot_hash ~ '^sha256:[0-9a-f]{64}$'),
 raw_body bytea NOT NULL CHECK(octet_length(raw_body) BETWEEN 17 AND 8388608),
 root_count integer NOT NULL CHECK(root_count BETWEEN 0 AND 10000),
 CHECK(snapshot_hash='sha256:'||encode(pg_catalog.sha256(raw_body),'hex')),
 PRIMARY KEY(org_id,project_id,snapshot_hash));
CREATE TABLE aos_capacity_publication_private.origin(
 org_id text NOT NULL CHECK(org_id='org-org'),project_id text NOT NULL CHECK(project_id='dev-project'),
 content_hash text NOT NULL CHECK(content_hash ~ '^[0-9a-f]{64}$'),
 raw_body bytea NOT NULL CHECK(octet_length(raw_body) BETWEEN 1 AND 2097152),
 signature bytea NOT NULL CHECK(octet_length(signature)=64),
 anchor_revision text NOT NULL,snapshot_hash text NOT NULL,
 CHECK(content_hash=encode(pg_catalog.sha256(raw_body),'hex')),
 PRIMARY KEY(org_id,project_id,content_hash),
 FOREIGN KEY(org_id,project_id,anchor_revision) REFERENCES aos_capacity_publication_private.deployment_anchor,
 FOREIGN KEY(org_id,project_id,snapshot_hash) REFERENCES aos_capacity_publication_private.root_snapshot);
CREATE TABLE aos_capacity_publication_private.root_entry(
 org_id text NOT NULL CHECK(org_id='org-org'),project_id text NOT NULL CHECK(project_id='dev-project'),
 snapshot_hash text NOT NULL,root_ordinal integer NOT NULL CHECK(root_ordinal BETWEEN 1 AND 10000),
 publisher_literal text NOT NULL,key_id_literal text NOT NULL,
 publisher_codepoints integer[] NOT NULL,key_id_codepoints integer[] NOT NULL,
 public_key bytea NOT NULL CHECK(octet_length(public_key)=32),
 root_revision text NOT NULL CHECK(root_revision ~ '^sha256:[0-9a-f]{64}$'),
 not_before timestamptz NOT NULL,not_after timestamptz NOT NULL,revoked_at timestamptz,
 canonical_root bytea NOT NULL CHECK(octet_length(canonical_root) BETWEEN 1 AND 8388608),
 CHECK(not_before<not_after),
 CHECK(publisher_codepoints=aos_capacity_publication_private.read_root_identifier_literal(publisher_literal)),
 CHECK(key_id_codepoints=aos_capacity_publication_private.read_root_identifier_literal(key_id_literal)),
 PRIMARY KEY(org_id,project_id,snapshot_hash,root_ordinal),
 UNIQUE(org_id,project_id,snapshot_hash,publisher_codepoints,key_id_codepoints),
 FOREIGN KEY(org_id,project_id,snapshot_hash) REFERENCES aos_capacity_publication_private.root_snapshot);
CREATE TABLE aos_capacity_publication_private.registry_epoch(
 org_id text NOT NULL CHECK(org_id='org-org'),project_id text NOT NULL CHECK(project_id='dev-project'),
 anchor_revision text NOT NULL,epoch bigint NOT NULL DEFAULT 0 CHECK(epoch>=0),
 head_origin_hash text,
 PRIMARY KEY(org_id,project_id),
 FOREIGN KEY(org_id,project_id,anchor_revision) REFERENCES aos_capacity_publication_private.deployment_anchor,
 FOREIGN KEY(org_id,project_id,head_origin_hash) REFERENCES aos_capacity_publication_private.origin);
"""

IMMUTABLE_SQL = r"""
CREATE FUNCTION aos_capacity_publication_private.immutable_registry_row()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $body$
BEGIN
 RAISE EXCEPTION 'CAPACITY_PUBLICATION_IMMUTABLE' USING ERRCODE='42501';
END
$body$;
REVOKE ALL ON FUNCTION aos_capacity_publication_private.immutable_registry_row() FROM PUBLIC;
"""


def install_registry_schema(execute):
    """One additive migration; no rows, LOGIN, crypto grants, or public entry."""
    for role in (OWNER, PUBLISHER):
        execute(reserved_role_sql(role))
    execute(f'CREATE SCHEMA {SCHEMA} AUTHORIZATION {OWNER}')
    execute(f'REVOKE ALL ON SCHEMA {SCHEMA} FROM PUBLIC,{PUBLISHER},aos_runtime,aos_provider_capacity_issuer')
    execute(CAPACITY_ROOT_IDENTIFIER_PROFILE_SQL)
    execute(CAPACITY_ROOT_SNAPSHOT_PROFILE_SQL)
    execute(IMMUTABLE_SQL)
    for signature in ('read_root_identifier_literal(text)', 'read_root_time_literal(text)',
                      'read_root_snapshot(bytea)', 'immutable_registry_row()'):
        execute(f'ALTER FUNCTION {SCHEMA}.{signature} OWNER TO {OWNER}')
        execute(f'REVOKE ALL ON FUNCTION {SCHEMA}.{signature} FROM PUBLIC,{PUBLISHER},aos_runtime,aos_provider_capacity_issuer')
    execute(TABLE_SQL)
    for table in TABLES:
        execute(f'ALTER TABLE {SCHEMA}.{table} OWNER TO {OWNER}')
        execute(f'REVOKE ALL ON {SCHEMA}.{table} FROM PUBLIC,{PUBLISHER},aos_runtime,aos_provider_capacity_issuer')
        execute(f'ALTER TABLE {SCHEMA}.{table} ENABLE ROW LEVEL SECURITY')
        execute(f'ALTER TABLE {SCHEMA}.{table} FORCE ROW LEVEL SECURITY')
        execute(f"""CREATE POLICY registry_positive_scope ON {SCHEMA}.{table} TO {OWNER}
          USING(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
          WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
        if table != 'registry_epoch':
            execute(f'CREATE TRIGGER immutable_registry_row BEFORE UPDATE OR DELETE ON {SCHEMA}.{table} '
                    f'FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.immutable_registry_row()')

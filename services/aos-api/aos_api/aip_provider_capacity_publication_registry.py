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


ORIGIN_REGISTRATION_SQL = r"""
CREATE FUNCTION aos_capacity_publication_private.register_origin(
 p_body bytea,p_signature bytea,p_roots bytea)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog
 SET work_mem='4MB' AS $body$
DECLARE
 doc jsonb;
 anchor aos_capacity_publication_private.deployment_anchor%ROWTYPE;
 fence aos_capacity_publication_private.registry_epoch%ROWTYPE;
 replay_valid boolean;
 snapshot_id text;
 origin_id text;
 observed_oid oid;
 observed_cluster text;
 root_total integer;
BEGIN
 IF session_user<>'aos_provider_capacity_policy_publisher'
   OR current_user<>'aos_capacity_publication_owner'
   OR current_setting('aos.org_id',true) IS DISTINCT FROM 'org-org'
   OR current_setting('aos.project_id',true) IS DISTINCT FROM 'dev-project'
   OR p_signature IS NULL OR octet_length(p_signature)<>64
   OR p_roots IS NULL OR octet_length(p_roots)>8388608 THEN
   RAISE EXCEPTION 'CAPACITY_ORIGIN_REGISTRATION_DENIED' USING ERRCODE='42501';
 END IF;
 IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=session_user AND
     (rolinherit OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls))
   OR EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid=session_user::regrole OR member=session_user::regrole) THEN
   RAISE EXCEPTION 'CAPACITY_ORIGIN_REGISTRATION_DENIED' USING ERRCODE='42501';
 END IF;
 SELECT * INTO fence FROM aos_capacity_publication_private.registry_epoch
   WHERE org_id='org-org' AND project_id='dev-project' FOR UPDATE;
 IF NOT FOUND THEN
   RAISE EXCEPTION 'CAPACITY_ORIGIN_REGISTRATION_DENIED' USING ERRCODE='42501';
 END IF;
 SELECT * INTO anchor FROM aos_capacity_publication_private.deployment_anchor
   WHERE org_id='org-org' AND project_id='dev-project' AND anchor_revision=fence.anchor_revision FOR SHARE;
 IF NOT FOUND THEN
   RAISE EXCEPTION 'CAPACITY_ORIGIN_REGISTRATION_DENIED' USING ERRCODE='42501';
 END IF;
 doc := aos_capacity_publication_private.read_origin_bootstrap(p_body);
 SELECT oid INTO observed_oid FROM pg_database WHERE datname=current_database();
 SELECT system_identifier::text INTO observed_cluster FROM pg_control_system();
 snapshot_id := 'sha256:'||encode(sha256(p_roots),'hex');
 origin_id := encode(sha256(p_body),'hex');
 IF doc->>'anchorRevision' IS DISTINCT FROM anchor.anchor_revision
   OR doc->>'publisher' IS DISTINCT FROM anchor.signer_publisher
   OR doc->>'keyId' IS DISTINCT FROM anchor.signer_key_id
   OR doc->>'publisherSubject' IS DISTINCT FROM anchor.publisher_subject
   OR doc->'deploymentTarget' IS DISTINCT FROM anchor.deployment_target
   OR doc->'deploymentTarget'->>'database' IS DISTINCT FROM current_database()
   OR (doc->'deploymentTarget'->>'databaseOid')::numeric IS DISTINCT FROM observed_oid::text::numeric
   OR doc->'deploymentTarget'->>'clusterIdentifier' IS DISTINCT FROM observed_cluster
   OR doc->>'rootSnapshotHash' IS DISTINCT FROM snapshot_id
   OR clock_timestamp()<aos_capacity_publication_private.read_signed_time(doc->'validFrom')
   OR clock_timestamp()>=aos_capacity_publication_private.read_signed_time(doc->'validUntil') THEN
   RAISE EXCEPTION 'CAPACITY_ORIGIN_REGISTRATION_DENIED' USING ERRCODE='42501';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
   JOIN pg_language l ON l.oid=p.prolang JOIN pg_roles r ON r.oid=p.proowner
   WHERE n.nspname='aos_ed25519' AND p.proname='verify'
     AND p.proargtypes='17 17 17'::oidvector AND p.prorettype='boolean'::regtype
     AND p.probin='$libdir/aos_ed25519' AND p.prosrc='aos_ed25519_verify'
     AND l.lanname='c' AND NOT p.prosecdef AND p.provolatile='i' AND p.proisstrict
     AND r.rolname='aos_ed25519_owner' AND n.nspowner=r.oid
     AND NOT (r.rolcanlogin OR r.rolinherit OR r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls)
     AND NOT EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid=r.oid OR member=r.oid)) THEN
   RAISE EXCEPTION 'CAPACITY_ORIGIN_VERIFIER_REQUIRED' USING ERRCODE='42501';
 END IF;
 IF aos_ed25519.verify(p_signature,p_body,anchor.signer_public_key) IS DISTINCT FROM true THEN
   RAISE EXCEPTION 'CAPACITY_ORIGIN_REGISTRATION_DENIED' USING ERRCODE='42501';
 END IF;
 -- The single materialized parse can spill to disk instead of retaining a
 -- composite array and its expanded copies in backend memory.
 IF fence.head_origin_hash IS NOT NULL THEN
   IF fence.epoch<>1 OR fence.head_origin_hash<>origin_id THEN
     RAISE EXCEPTION 'CAPACITY_ORIGIN_REGISTRATION_DENIED' USING ERRCODE='42501';
   END IF;
   WITH roots AS MATERIALIZED (
     SELECT 'org-org'::text AS org_id,'dev-project'::text AS project_id,snapshot_id AS snapshot_hash,r.*
       FROM aos_capacity_publication_private.read_root_snapshot(p_roots) r)
   SELECT EXISTS(
     SELECT 1 FROM aos_capacity_publication_private.origin o
     JOIN aos_capacity_publication_private.root_snapshot s USING(org_id,project_id,snapshot_hash)
     WHERE o.org_id='org-org' AND o.project_id='dev-project' AND o.content_hash=origin_id
       AND o.raw_body=p_body AND o.signature=p_signature AND o.anchor_revision=anchor.anchor_revision
       AND s.snapshot_hash=snapshot_id AND s.raw_body=p_roots AND s.root_count=(SELECT count(*) FROM roots))
     AND (SELECT count(*) FROM aos_capacity_publication_private.root_entry
       WHERE org_id='org-org' AND project_id='dev-project' AND snapshot_hash=snapshot_id)=(SELECT count(*) FROM roots)
     AND NOT EXISTS(SELECT * FROM aos_capacity_publication_private.root_entry
       WHERE org_id='org-org' AND project_id='dev-project' AND snapshot_hash=snapshot_id
       EXCEPT SELECT * FROM roots)
   INTO replay_valid;
   IF replay_valid IS DISTINCT FROM true
     OR clock_timestamp()>=aos_capacity_publication_private.read_signed_time(doc->'validUntil') THEN
     RAISE EXCEPTION 'CAPACITY_ORIGIN_REGISTRATION_DENIED' USING ERRCODE='42501';
   END IF;
   RETURN origin_id;
 END IF;
 IF fence.epoch<>0 THEN
   RAISE EXCEPTION 'CAPACITY_ORIGIN_REGISTRATION_DENIED' USING ERRCODE='42501';
 END IF;
 WITH roots AS MATERIALIZED (
   SELECT * FROM aos_capacity_publication_private.read_root_snapshot(p_roots)),
 snapshot_insert AS (
   INSERT INTO aos_capacity_publication_private.root_snapshot
     SELECT 'org-org','dev-project',snapshot_id,p_roots,count(*) FROM roots
     RETURNING org_id,project_id,snapshot_hash),
 origin_insert AS (
   INSERT INTO aos_capacity_publication_private.origin
     SELECT org_id,project_id,origin_id,p_body,p_signature,anchor.anchor_revision,snapshot_hash FROM snapshot_insert
     RETURNING org_id,project_id,snapshot_hash),
 root_insert AS (
   INSERT INTO aos_capacity_publication_private.root_entry
     SELECT o.org_id,o.project_id,o.snapshot_hash,r.* FROM roots r CROSS JOIN origin_insert o
     RETURNING root_ordinal)
 SELECT count(*) INTO root_total FROM root_insert;
 UPDATE aos_capacity_publication_private.registry_epoch SET epoch=1,head_origin_hash=origin_id
   WHERE org_id='org-org' AND project_id='dev-project';
 -- A fresh return-time check rolls back expired writes, but is not a
 -- final-COMMIT TTL guarantee.
 IF clock_timestamp()>=aos_capacity_publication_private.read_signed_time(doc->'validUntil') THEN
   RAISE EXCEPTION 'CAPACITY_ORIGIN_REGISTRATION_DENIED' USING ERRCODE='42501';
 END IF;
 RETURN origin_id;
END
$body$;
REVOKE ALL ON FUNCTION aos_capacity_publication_private.register_origin(bytea,bytea,bytea) FROM PUBLIC;
"""


def install_origin_registration(execute):
    """No anchor, LOGIN or crypto installation; missing verifier stays closed."""
    from aos_api.aip_provider_capacity_publication_store import (
        CAPACITY_SIGNED_BODY_PROFILE_SQL, CAPACITY_IDENTIFIER_PROFILE_SQL,
        CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL, CAPACITY_SIGNING_PERMIT_PROFILE_SQL,
        CAPACITY_ORIGIN_BOOTSTRAP_PROFILE_SQL,
    )
    for ddl in (CAPACITY_SIGNED_BODY_PROFILE_SQL,CAPACITY_IDENTIFIER_PROFILE_SQL,
                CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL,CAPACITY_SIGNING_PERMIT_PROFILE_SQL,
                CAPACITY_ORIGIN_BOOTSTRAP_PROFILE_SQL,ORIGIN_REGISTRATION_SQL):
        execute(ddl)
    execute(f"""DO $owner$ DECLARE f record; BEGIN
      FOR f IN SELECT p.oid::regprocedure AS signature FROM pg_proc p
        JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='{SCHEMA}' LOOP
        EXECUTE format('ALTER FUNCTION %s OWNER TO {OWNER}',f.signature);
        EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC,{PUBLISHER},aos_runtime,aos_provider_capacity_issuer',f.signature);
      END LOOP;
      IF to_regprocedure('aos_ed25519.verify(bytea,bytea,bytea)') IS NOT NULL THEN
        GRANT USAGE ON SCHEMA aos_ed25519 TO {OWNER};
        GRANT EXECUTE ON FUNCTION aos_ed25519.verify(bytea,bytea,bytea) TO {OWNER};
      END IF;
    END $owner$;""")
    execute(f'GRANT EXECUTE ON FUNCTION pg_catalog.pg_control_system() TO {OWNER}')
    execute(f'GRANT USAGE ON SCHEMA {SCHEMA} TO {PUBLISHER}')
    execute(f'GRANT EXECUTE ON FUNCTION {SCHEMA}.register_origin(bytea,bytea,bytea) TO {PUBLISHER}')

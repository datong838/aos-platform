DO $$
DECLARE r record;
BEGIN
  SELECT * INTO r FROM pg_catalog.pg_roles WHERE rolname='aos_ed25519_owner';
  IF NOT FOUND THEN
    CREATE ROLE aos_ed25519_owner NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB
      NOCREATEROLE NOREPLICATION NOBYPASSRLS;
  ELSIF r.rolcanlogin OR r.rolinherit OR r.rolsuper OR r.rolcreatedb
    OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls THEN
    RAISE EXCEPTION 'AOS_ED25519_OWNER_DRIFT';
  END IF;
  IF EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members WHERE roleid='aos_ed25519_owner'::regrole OR member='aos_ed25519_owner'::regrole)
    OR EXISTS(SELECT 1 FROM pg_catalog.pg_shdepend WHERE refclassid='pg_catalog.pg_authid'::regclass AND refobjid='aos_ed25519_owner'::regrole)
    OR EXISTS(SELECT 1 FROM pg_catalog.pg_class WHERE relowner='aos_ed25519_owner'::regrole)
    OR EXISTS(SELECT 1 FROM pg_catalog.pg_proc WHERE proowner='aos_ed25519_owner'::regrole)
    OR EXISTS(SELECT 1 FROM pg_catalog.pg_namespace WHERE nspowner='aos_ed25519_owner'::regrole)
    OR EXISTS(SELECT 1 FROM pg_catalog.pg_database WHERE datdba='aos_ed25519_owner'::regrole)
    OR EXISTS(SELECT 1 FROM pg_catalog.pg_class c,LATERAL aclexplode(c.relacl) a WHERE a.grantee='aos_ed25519_owner'::regrole)
    OR EXISTS(SELECT 1 FROM pg_catalog.pg_attribute c,LATERAL aclexplode(c.attacl) a WHERE a.grantee='aos_ed25519_owner'::regrole)
    OR EXISTS(SELECT 1 FROM pg_catalog.pg_proc c,LATERAL aclexplode(c.proacl) a WHERE a.grantee='aos_ed25519_owner'::regrole)
    OR EXISTS(SELECT 1 FROM pg_catalog.pg_namespace c,LATERAL aclexplode(c.nspacl) a WHERE a.grantee='aos_ed25519_owner'::regrole)
    OR EXISTS(SELECT 1 FROM pg_catalog.pg_database c,LATERAL aclexplode(c.datacl) a WHERE a.grantee='aos_ed25519_owner'::regrole) THEN
    RAISE EXCEPTION 'AOS_ED25519_OWNER_DRIFT';
  END IF;
END $$;

CREATE FUNCTION aos_ed25519.verify(signature bytea, message bytea, public_key bytea)
RETURNS boolean AS 'MODULE_PATHNAME', 'aos_ed25519_verify'
LANGUAGE C IMMUTABLE STRICT PARALLEL SAFE SECURITY INVOKER;
ALTER FUNCTION aos_ed25519.verify(bytea,bytea,bytea) OWNER TO aos_ed25519_owner;
ALTER SCHEMA aos_ed25519 OWNER TO aos_ed25519_owner;
REVOKE ALL ON SCHEMA aos_ed25519 FROM PUBLIC;
REVOKE ALL ON FUNCTION aos_ed25519.verify(bytea,bytea,bytea) FROM PUBLIC;

-- No arm, completion or dispatch permission is provided by this version.
DO $owner$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles
    WHERE rolname='aos_physical_capacity_occupation_owner'
      AND NOT rolcanlogin AND NOT rolinherit AND NOT rolsuper
      AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication AND NOT rolbypassrls)
    OR EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members
      WHERE member='aos_physical_capacity_occupation_owner'::pg_catalog.regrole
         OR roleid='aos_physical_capacity_occupation_owner'::pg_catalog.regrole) THEN
    RAISE EXCEPTION 'SHARED_ADMISSION_NATIVE_OWNER_REQUIRED' USING ERRCODE='42501';
  END IF;
END
$owner$;
ALTER SCHEMA aos_admission_native_private OWNER TO aos_physical_capacity_occupation_owner;
REVOKE ALL ON SCHEMA aos_admission_native_private FROM PUBLIC;
CREATE FUNCTION aos_admission_native_private.pending_relations()
RETURNS oid[] AS 'MODULE_PATHNAME', 'aos_admission_pending_relations'
LANGUAGE c VOLATILE PARALLEL UNSAFE SECURITY INVOKER SET search_path=pg_catalog;
ALTER FUNCTION aos_admission_native_private.pending_relations()
OWNER TO aos_physical_capacity_occupation_owner;
REVOKE ALL ON FUNCTION aos_admission_native_private.pending_relations() FROM PUBLIC;

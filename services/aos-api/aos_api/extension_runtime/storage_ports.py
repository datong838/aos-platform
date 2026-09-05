"""Trusted broker transaction guard; not an arbitrary SQL execution port."""
from aos_api.extension_runtime.lifecycle_store import _require_transaction, _values


class StorageRoleDenied(PermissionError):
    pass


def require_runtime_role(conn, *, org_id, project_id, protected_tables):
    _require_transaction(conn)
    if not org_id or not project_id or not protected_tables:
        raise StorageRoleDenied("trusted scope and protected tables required")
    role=conn.execute("""SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_roles
        WHERE (rolsuper OR rolbypassrls) AND
          (pg_catalog.pg_has_role(current_user,oid,'MEMBER') OR
           pg_catalog.pg_has_role(session_user,oid,'MEMBER'))) AS unsafe""").fetchone()
    if _values(role,("unsafe",))[0]:
        raise StorageRoleDenied("privileged runtime connection prohibited")
    scope=conn.execute("""SELECT current_setting('aos.org_id',true) AS org_id,
        current_setting('aos.project_id',true) AS project_id""").fetchone()
    if _values(scope,("org_id","project_id"))!=(org_id,project_id):
        raise StorageRoleDenied("runtime tenant scope mismatch")
    for table in protected_tables:
        # Identifiers are resolved as values, never interpolated into SQL.
        row=conn.execute("""SELECT c.relrowsecurity,c.relforcerowsecurity,
            pg_catalog.pg_has_role(current_user,c.relowner,'MEMBER') OR
            pg_catalog.pg_has_role(session_user,c.relowner,'MEMBER') AS owns
            FROM pg_catalog.pg_class c WHERE c.oid=pg_catalog.to_regclass(%s)""",(table,)).fetchone()
        if row is None:
            raise StorageRoleDenied("protected relation missing")
        rls,forced,owns=_values(row,("relrowsecurity","relforcerowsecurity","owns"))
        if not rls or not forced or owns:
            raise StorageRoleDenied("runtime role or relation isolation invalid")

"""Trusted broker transaction guard; not an arbitrary SQL execution port."""
from aos_api.extension_runtime.lifecycle_store import _require_transaction, _values
import re
from psycopg import sql


class StorageRoleDenied(PermissionError):
    pass


def require_registry_relation(conn, *, table, column_types):
    """Lock and check physical scalar storage; not a tenant/role authorization.

    Execution must additionally use ONLY to exclude concurrently attached children.
    The broker owns the transaction and sets its bounded lock/statement timeout.
    """
    _require_transaction(conn)
    parts = table.split(".") if isinstance(table, str) else []
    if (len(parts) != 2 or any(not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", p) for p in parts)
            or not column_types or len(column_types) > 64
            or any(t not in {"int8", "text", "bool"} for t in column_types.values())):
        raise StorageRoleDenied("invalid registry relation contract")
    conn.execute(sql.SQL("LOCK TABLE ONLY {} IN ACCESS SHARE MODE").format(sql.Identifier(*parts)))
    row = conn.execute("""SELECT c.relkind,c.relhassubclass
        FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname=%s AND c.relname=%s""", tuple(parts)).fetchone()
    if row is None or _values(row, ("relkind", "relhassubclass")) != ("r", False):
        raise StorageRoleDenied("only non-inherited physical tables supported")
    rows = conn.execute("""SELECT a.attname,t.typname,n.nspname
        FROM pg_catalog.pg_attribute a
        JOIN pg_catalog.pg_type t ON t.oid=a.atttypid
        JOIN pg_catalog.pg_namespace n ON n.oid=t.typnamespace
        WHERE a.attrelid=pg_catalog.to_regclass(%s) AND a.attnum>0 AND NOT a.attisdropped""",
        (table,)).fetchall()
    actual = {name: (kind, namespace) for name, kind, namespace in
              (_values(row, ("attname", "typname", "nspname")) for row in rows)}
    if any(actual.get(name) != (kind, "pg_catalog") for name, kind in column_types.items()):
        raise StorageRoleDenied("registry column type mismatch")


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

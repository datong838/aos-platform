"""Trusted broker transaction guard; not an arbitrary SQL execution port."""
from aos_api.extension_runtime.lifecycle_store import _require_transaction, _values
import re
import json
import uuid
from time import monotonic
from psycopg import sql
from psycopg.pq import TransactionStatus
from aos_api.extension_runtime.query_registry import validate_select_template, validate_parameter


class StorageRoleDenied(PermissionError):
    pass


def read_registered_rows(conn, *, raw, expected_hash, table, column_types,
                         parameter, org_id, project_id, limit=100):
    """Internal broker primitive, after signed admission and epoch authorization.

    No router/IPC exposes this function. Scope and registry metadata are trusted
    broker inputs, never values supplied by an extension process.
    """
    if not conn.autocommit or conn.info.transaction_status != TransactionStatus.IDLE:
        raise StorageRoleDenied("dedicated idle connection required")
    if type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError("invalid row limit")
    deadline = monotonic() + 10.0
    column_types = dict(column_types)
    template = validate_select_template(raw, expected_hash=expected_hash,
        tables={table: frozenset(column_types)}, parameter_count=1)
    parameter = validate_parameter(column_types[template.predicate_column], parameter)
    with conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        conn.execute("SELECT pg_catalog.set_config('search_path','pg_catalog',true), "
                     "pg_catalog.set_config('statement_timeout','10000',true), "
                     "pg_catalog.set_config('lock_timeout','1000',true), "
                     "pg_catalog.set_config('aos.org_id',%s,true), "
                     "pg_catalog.set_config('aos.project_id',%s,true)", (org_id, project_id))
        def remaining_budget():
            remaining = int((deadline - monotonic()) * 1000)
            if remaining <= 0:
                raise TimeoutError("registry read deadline exceeded")
            conn.execute("SELECT pg_catalog.set_config('statement_timeout',%s,true)", (str(remaining),))

        class BudgetedConnection:
            info = conn.info

            def execute(self, *args, **kwargs):
                remaining_budget()
                return conn.execute(*args, **kwargs)

        guarded = BudgetedConnection()
        require_registry_relation(guarded, table=table, column_types=column_types)
        require_runtime_role(guarded, org_id=org_id, project_id=project_id, protected_tables=(table,))

        projections = [sql.SQL("pg_catalog.left({},4097)").format(sql.Identifier(name))
                       if column_types[name] == "text" else sql.Identifier(name)
                       for name in template.columns]
        query = sql.SQL("SELECT {} FROM ONLY {} WHERE {} {} %s LIMIT %s").format(
            sql.SQL(",").join(projections), sql.Identifier(*table.split(".")),
            sql.Identifier(template.predicate_column), sql.SQL(template.operator))
        rows, size = [], 0
        with conn.cursor(name="registry_"+uuid.uuid4().hex) as cursor:
            remaining_budget()
            cursor.execute(query, (parameter, limit+1))
            while True:
                remaining_budget()
                row = cursor.fetchone()
                if row is None:
                    break
                if isinstance(row, dict):
                    raise StorageRoleDenied("tuple row factory required")
                if any(isinstance(value, str) and len(value.encode("utf-8")) > 4096 for value in row):
                    raise ValueError("result value exceeds byte limit")
                size += len(json.dumps(row, ensure_ascii=False).encode("utf-8"))
                if len(rows) >= limit or size > 1024*1024:
                    raise ValueError("result exceeds registry limit")
                rows.append(tuple(row))
        if monotonic() >= deadline:
            raise TimeoutError("registry read deadline exceeded")
        return tuple(rows)


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

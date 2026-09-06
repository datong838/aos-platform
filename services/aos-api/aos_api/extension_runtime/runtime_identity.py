"""Database-observed identity preflight for the three production connection planes."""
from dataclasses import dataclass

from psycopg.pq import TransactionStatus


@dataclass(frozen=True, slots=True)
class RuntimeDatabaseIdentity:
    authority: tuple[str, int, str]
    session_user: str
    role_oid: int
    directory_member: bool
    runtime_member: bool
    privileged: bool
    owns_protected_relation: bool


def probe_runtime_database_identity(conn, *, protected_relations: tuple[str, ...]) -> RuntimeDatabaseIdentity:
    if type(protected_relations) is not tuple or not protected_relations or any(
        type(name) is not str or not name for name in protected_relations
    ):
        raise ValueError("exact protected relation names required")
    if len(protected_relations) != len(set(protected_relations)):
        raise ValueError("duplicate protected relation names")
    if conn.info.transaction_status != TransactionStatus.IDLE:
        raise RuntimeError("database identity probe requires an idle connection")
    with conn.transaction():
        row = conn.execute(
            """SELECT coalesce(inet_server_addr()::text,'local') AS server_addr,
                      inet_server_port() AS server_port,current_database() AS database_name,
                      session_user AS session_user,current_user AS current_user,
                      role.oid AS role_oid,role.rolsuper,role.rolbypassrls,
                      pg_has_role(session_user,'aos_extension_directory','member') AS directory_member,
                      pg_has_role(session_user,'aos_runtime','member') AS runtime_member,
                      (SELECT count(*) FROM pg_class relation
                         JOIN pg_namespace namespace ON namespace.oid=relation.relnamespace
                        WHERE namespace.nspname='public' AND relation.relname=ANY(%s))
                        AS protected_relation_count,
                      EXISTS(SELECT 1 FROM pg_class relation
                              JOIN pg_namespace namespace ON namespace.oid=relation.relnamespace
                             WHERE namespace.nspname='public' AND relation.relname=ANY(%s)
                               AND relation.relowner=role.oid) AS owns_protected_relation
                 FROM pg_roles role WHERE role.rolname=session_user""",
            (list(protected_relations), list(protected_relations)),
        ).fetchone()
    if row is None:
        raise RuntimeError("database session identity is unavailable")
    value = lambda key, offset: row[key] if isinstance(row, dict) else row[offset]
    session_user = value("session_user", 3)
    if value("current_user", 4) != session_user:
        raise RuntimeError("database connection must begin without an adopted role")
    if value("protected_relation_count", 10) != len(protected_relations):
        raise RuntimeError("protected database relation is unavailable")
    port = value("server_port", 1)
    return RuntimeDatabaseIdentity(
        authority=(value("server_addr", 0), 0 if port is None else port, value("database_name", 2)),
        session_user=session_user,
        role_oid=value("role_oid", 5),
        directory_member=value("directory_member", 8) is True,
        runtime_member=value("runtime_member", 9) is True,
        privileged=value("rolsuper", 6) is True or value("rolbypassrls", 7) is True,
        owns_protected_relation=value("owns_protected_relation", 11) is True,
    )


def require_isolated_runtime_identities(
    *, directory: RuntimeDatabaseIdentity, runtime: RuntimeDatabaseIdentity,
    web: RuntimeDatabaseIdentity,
) -> None:
    if any(type(item) is not RuntimeDatabaseIdentity for item in (directory, runtime, web)):
        raise TypeError("exact runtime database identities required")
    if len({directory.authority, runtime.authority, web.authority}) != 1:
        raise RuntimeError("runtime planes must use the same database authority")
    principals = {(item.session_user, item.role_oid) for item in (directory, runtime, web)}
    if len(principals) != 3:
        raise RuntimeError("directory, runtime and web database principals must differ")
    if any(item.privileged or item.owns_protected_relation for item in (directory, runtime, web)):
        raise RuntimeError("runtime database principals must be non-privileged non-owners")
    if not directory.directory_member or directory.runtime_member:
        raise RuntimeError("directory database principal has invalid memberships")
    if not runtime.runtime_member or runtime.directory_member:
        raise RuntimeError("runtime worker database principal has invalid memberships")
    if web.directory_member or web.runtime_member:
        raise RuntimeError("web database principal must not inherit runtime memberships")

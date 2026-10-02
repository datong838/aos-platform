"""Exact shared-schema receipts; maintenance-only callback, never an SDK port."""
from dataclasses import dataclass
import inspect
import re

from .lifecycle_store import _require_transaction,_values,RuntimeConflict


@dataclass(frozen=True)
class SchemaRequirement:
    package_id:str
    schema_version:str
    migration_hash:str

    def __post_init__(self):
        for value,pattern in (
            (self.package_id,r"[a-z][a-z0-9_.-]{0,159}"),
            (self.schema_version,r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}"),
            (self.migration_hash,r"sha256:[0-9a-f]{64}"),
        ):
            if type(value) is not str or not re.fullmatch(pattern,value):
                raise ValueError("invalid exact schema requirement")


def _installed(conn,requirement):
    if not isinstance(requirement,SchemaRequirement):
        raise ValueError("typed schema requirement required")
    row=conn.execute("""SELECT migration_hash FROM extension_schema_installation
        WHERE package_id=%s AND schema_version=%s""",(requirement.package_id,requirement.schema_version)).fetchone()
    if row is None:
        return False
    if _values(row,("migration_hash",))[0]!=requirement.migration_hash:
        raise RuntimeConflict("same schema version has another migration digest")
    return True


def require_installed(conn,requirements):
    """Read only: newer versions do not implicitly satisfy an exact requirement."""
    _require_transaction(conn)
    requirements=tuple(requirements)
    if not 1<=len(requirements)<=64:
        raise ValueError("bounded schema requirements required")
    for requirement in requirements:
        if not _installed(conn,requirement):
            raise LookupError("required schema migration is not installed")


def apply_once(conn,requirement,apply):
    """Trusted approved maintenance runner owns this transaction and callback."""
    _require_transaction(conn)
    if not isinstance(requirement,SchemaRequirement) or not callable(apply):
        raise ValueError("typed requirement and trusted callback required")
    allowed=conn.execute("""SELECT current_user AS role,
        has_table_privilege(current_user,'extension_schema_installation','INSERT') AS allowed""").fetchone()
    role,can_insert=_values(allowed,("role","allowed"))
    if role=='aos_runtime' or not can_insert:
        raise PermissionError("maintenance schema role required")
    # Shared physical schema, not per-tenant or per-container migration execution.
    conn.execute("SELECT pg_advisory_xact_lock(2314,1)")
    if _installed(conn,requirement):
        return False
    result=apply(conn)
    if result is not None:
        if inspect.iscoroutine(result):
            result.close()
        raise ValueError("migration callback must complete synchronously and return None")
    conn.execute("""INSERT INTO extension_schema_installation(package_id,schema_version,migration_hash)
        VALUES(%s,%s,%s)""",(requirement.package_id,requirement.schema_version,requirement.migration_hash))
    return True

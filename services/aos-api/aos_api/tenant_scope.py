"""TI-1 canonical tenant scope and transaction-local PostgreSQL context."""
from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from importlib import resources
from typing import Any

MAX_SCOPE_PART_LENGTH = 160
ORG_GUC = "aos.org_id"
PROJECT_GUC = "aos.project_id"
RUNTIME_DB_ROLE = "aos_runtime"


@dataclass(frozen=True, slots=True)
class TenantScope:
    org_id: str
    project_id: str

    def __post_init__(self) -> None:
        _validate_scope_part("org_id", self.org_id)
        _validate_scope_part("project_id", self.project_id)

    @property
    def key(self) -> tuple[str, str]:
        return self.org_id, self.project_id

    @classmethod
    def from_workspace(cls, *, org_id: str, workspace_id: str) -> TenantScope:
        """Translate the e-commerce workspace alias at the adapter boundary."""
        return cls(org_id=org_id, project_id=workspace_id)


_current_scope: ContextVar[TenantScope | None] = ContextVar(
    "tenant_scope", default=None
)


def current_tenant_scope() -> TenantScope | None:
    return _current_scope.get()


def require_tenant_scope() -> TenantScope:
    scope = current_tenant_scope()
    if scope is None:
        raise RuntimeError("tenant scope is required")
    return scope


@contextmanager
def bind_tenant_scope(scope: TenantScope) -> Iterator[TenantScope]:
    token = _current_scope.set(scope)
    try:
        yield scope
    finally:
        _current_scope.reset(token)


def apply_transaction_scope(conn: Any, scope: TenantScope) -> None:
    """Set transaction-local role and GUCs.

    Both the role and the tenant GUCs are transaction-local on purpose: a
    session-scoped setting would leak the previous caller's tenant into the
    next statement. The cost is the inverse discipline — any intermediate
    ``commit()``/``rollback()`` discards them, after which ``current_user``
    reverts to the NOINHERIT login (every table denies) and the RLS policy sees
    no ``aos.org_id`` (every row is filtered out). Do the whole unit of work in
    one transaction; use :func:`apply_platform_role` for cross-tenant paths.
    """
    conn.execute(f"SET LOCAL ROLE {RUNTIME_DB_ROLE}")
    conn.execute(
        """
        SELECT set_config('aos.org_id', %s, true),
               set_config('aos.project_id', %s, true)
        """,
        scope.key,
    )


def apply_platform_role(conn: Any) -> None:
    """Adopt the runtime DB role WITHOUT tenant GUCs.

    The connection user is NOINHERIT (``aos_a0v_runtime_*``), so a scope-less
    connection never adopts ``aos_runtime`` and is denied on any table the
    runtime role owns or was granted. Paths that legitimately work across
    tenants — bootstrap DDL probes, the membership catalog load — still need
    the role, they just must not carry a tenant GUC.

    Session-scoped on purpose (``SET ROLE``, not ``SET LOCAL ROLE``): a LOCAL
    role is discarded by any intermediate COMMIT, after which ``current_user``
    silently reverts to the NOINHERIT login and the very next statement raises
    "permission denied for table ..." (verified — this is what broke
    ``ensure_system_meta``, whose seed helpers commit midway). Platform
    connections are always freshly created and carry no tenant state, so a
    session-scoped role cannot leak across callers.

    Only use for platform-level maintenance on tables that are **not** guarded
    by tenant RLS. Tenant-scoped reads/writes must go through
    ``apply_transaction_scope`` so the RLS policy can see the GUCs.
    """
    conn.execute(f"SET ROLE {RUNTIME_DB_ROLE}")


def filter_by_tenant(
    items: list[dict[str, Any]],
    org_id: str,
    project_id: str,
    *,
    org_key: str = "orgId",
    project_key: str = "projectId",
) -> list[dict[str, Any]]:
    """Compatibility helper retained from the TWA.5 public contract."""
    return [
        item
        for item in items
        if item.get(org_key) == org_id and item.get(project_key) == project_id
    ]


def belongs_to_tenant(
    item: dict[str, Any] | None,
    org_id: str,
    project_id: str,
    *,
    org_key: str = "orgId",
    project_key: str = "projectId",
) -> bool:
    if not item:
        return False
    return item.get(org_key) == org_id and item.get(project_key) == project_id


def load_tenant_ledger() -> dict[str, Any]:
    raw = resources.files("aos_api").joinpath("tenant_ledger.json").read_text(
        encoding="utf-8"
    )
    return json.loads(raw)


def p0_open_gaps(
    ledger: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    data = ledger or load_tenant_ledger()
    return [
        entry
        for entry in data.get("entries", [])
        if entry.get("priority") == "P0" and entry.get("status") == "GAP"
    ]


def _validate_scope_part(field: str, value: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    if not value or value != value.strip():
        raise ValueError(f"{field} must be non-empty and trimmed")
    if len(value) > MAX_SCOPE_PART_LENGTH:
        raise ValueError(f"{field} exceeds {MAX_SCOPE_PART_LENGTH} characters")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError(f"{field} contains control characters")

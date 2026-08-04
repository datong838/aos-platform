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
    """Set transaction-local GUCs; values disappear at transaction end."""
    conn.execute(f"SET LOCAL ROLE {RUNTIME_DB_ROLE}")
    conn.execute(
        """
        SELECT set_config('aos.org_id', %s, true),
               set_config('aos.project_id', %s, true)
        """,
        scope.key,
    )


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

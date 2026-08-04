from __future__ import annotations

import pytest
from aos_api.tenant_scope import (
    TenantScope,
    apply_transaction_scope,
    bind_tenant_scope,
    current_tenant_scope,
    require_tenant_scope,
)


class FakeConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[str, str] | None]] = []

    def execute(
        self, query: str, values: tuple[str, str] | None = None
    ) -> None:
        self.calls.append((query, values))


@pytest.mark.parametrize(
    "value",
    ["", " org", "org ", "org\nother", "x" * 161],
)
def test_tenant_scope_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(ValueError):
        TenantScope(org_id=value, project_id="project")


def test_tenant_scope_context_is_nested_and_reset() -> None:
    outer = TenantScope("org-a", "project-a")
    inner = TenantScope("org-b", "project-b")

    assert current_tenant_scope() is None
    with bind_tenant_scope(outer):
        assert require_tenant_scope() == outer
        with bind_tenant_scope(inner):
            assert require_tenant_scope() == inner
        assert require_tenant_scope() == outer
    assert current_tenant_scope() is None
    with pytest.raises(RuntimeError, match="tenant scope is required"):
        require_tenant_scope()


def test_workspace_alias_maps_to_canonical_project_id() -> None:
    scope = TenantScope.from_workspace(org_id="org-a", workspace_id="workspace-a")
    assert scope.key == ("org-a", "workspace-a")


def test_apply_scope_uses_transaction_local_set_config() -> None:
    conn = FakeConnection()
    scope = TenantScope("org-a", "project-a")

    apply_transaction_scope(conn, scope)

    assert conn.calls == [
        ("SET LOCAL ROLE aos_runtime", None),
        (
            """
        SELECT set_config('aos.org_id', %s, true),
               set_config('aos.project_id', %s, true)
        """,
            scope.key,
        )
    ]
    assert "true" in conn.calls[1][0]

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from aos_api.db import connect
from aos_api.module_events import list_events
from aos_api.module_identity import (
    ModuleIdentityDriftError,
    resolve_module_pk,
    stable_module_pk,
)
from aos_api.tenant_scope import TenantScope


class _Result:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[dict[str, object]]:
        return self._rows


class _Connection:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, statement: str, params: tuple[object, ...]) -> _Result:
        self.calls.append((statement, params))
        return _Result(self.rows)


def test_identity_resolution_compares_stable_and_legacy_keys() -> None:
    scope = TenantScope("org-a", "project-a")
    module_id = "orders"
    expected = stable_module_pk(*scope.key, module_id)
    conn = _Connection(
        [{"id": module_id, "module_id": module_id, "module_pk": expected}]
    )

    assert resolve_module_pk(conn, scope, module_id) == expected
    statement, params = conn.calls[0]
    assert "module_pk=%s OR id=%s" in statement
    assert params == (*scope.key, expected, module_id)


def test_identity_resolution_fails_closed_on_drift() -> None:
    scope = TenantScope("org-a", "project-a")
    conn = _Connection(
        [{"id": "orders", "module_id": "orders", "module_pk": None}]
    )

    with pytest.raises(ModuleIdentityDriftError):
        resolve_module_pk(conn, scope, "orders")


def test_child_business_predicates_use_module_pk() -> None:
    root = Path(__file__).resolve().parents[2] / "aos_api"
    files = (
        "canvas_config.py",
        "module_deployments.py",
        "module_events.py",
        "module_interfaces.py",
        "module_queries.py",
        "module_variables.py",
        "widget_instances.py",
    )
    for name in files:
        source = (root / name).read_text(encoding="utf-8")
        assert "WHERE module_id=%s" not in source, name
        assert "WHERE module_id = %s" not in source, name
        assert "AND module_id=%s" not in source, name
        assert "module_pk=%s" in source, name


def test_orphan_event_is_hidden_without_parent_module() -> None:
    with connect() as conn:
        revision = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    if revision and revision["version_num"] in {
        "228ti2e7contract",
        "228ti3e1expand",
        "228ti3e4validate",
        "228ti3e6rls",
            "228ti3e7contract",
            "228ti4c1expand",
            "228ti4d1expand",
            "228ti4d4validate",
            "228ti4d6rls",
            "228ti4d7contract",
            "228ti4c3contract",
            "228ti4a1apollo",
            "228ti5a1aip",
            "228ti5a2kv",
            "228ti5a3lineage",
            "228ti5b1models",
            "228ti6bcontract",
            "228ti6cassets",
            "228ti6drelations",
        }:
        pytest.skip("E7 rejects new orphan rows; quarantine is covered by E7 tests")
    suffix = uuid.uuid4().hex
    scope = TenantScope(f"org-orphan-{suffix}", f"project-orphan-{suffix}")
    module_id = f"orphan-{suffix}"
    event_id = f"event-{suffix}"
    with connect(scope) as conn:
        conn.execute(
            "INSERT INTO module_events "
            "(id,module_id,name,trigger_config,action_config,enabled,sort_order,"
            "org_id,project_id,module_pk) "
            "VALUES (%s,%s,'orphan','{}'::jsonb,'{}'::jsonb,true,0,%s,%s,NULL)",
            (event_id, module_id, *scope.key),
        )
        conn.commit()

    assert list_events(scope, module_id) == []

"""TI-6-4 registry-driven cleanup impact plans and rollback-only drills."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any

import psycopg
from psycopg import sql

from aos_api.tenant_resource_registry import (
    load_tenant_resource_registry,
    validate_registry,
)
from aos_api.tenant_scope import TenantScope

DELETE_SCOPED_ROWS = "DELETE_SCOPED_ROWS"
RETAIN_IMMUTABLE_HISTORY = "RETAIN_IMMUTABLE_HISTORY"
RETAIN_BROADER_SCOPE = "RETAIN_BROADER_SCOPE"
EXTERNAL_NOT_EXECUTED = "EXTERNAL_NOT_EXECUTED"
_SYNTHETIC_PREFIX = "ti6-synthetic-"
_DISPOSABLE_DATABASE_PREFIXES = ("aos_ti6_", "aos_test_")


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _business_resources(registry: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        (
            entry
            for entry in registry.get("resources", [])
            if isinstance(entry, dict)
            and entry.get("classification") == "TENANT_OWNED"
            and entry.get("baselineScope", "BUSINESS_DATA") == "BUSINESS_DATA"
        ),
        key=lambda entry: (int(entry.get("clearOrder", 100)), str(entry["name"])),
    )


def _scope_predicate(
    entry: dict[str, Any], scope: TenantScope
) -> tuple[Any, tuple[str, ...]]:
    columns = tuple(str(value) for value in entry.get("tenantColumns") or ())
    if columns == ("org_id", "project_id"):
        return sql.SQL("org_id=%s AND project_id=%s"), scope.key
    if columns == ("org_id", "workspace_id"):
        return sql.SQL("org_id=%s AND workspace_id=%s"), scope.key
    if columns == ("org_id",):
        return sql.SQL("org_id=%s"), (scope.org_id,)
    raise ValueError(
        f"{entry.get('name')} has unsupported tenant columns {list(columns)}"
    )


def _has_immutable_delete_guard(conn: Any, table_name: str) -> bool:
    row = conn.execute(
        """
        SELECT EXISTS (
          SELECT 1
            FROM pg_trigger trigger
            JOIN pg_class relation ON relation.oid=trigger.tgrelid
            JOIN pg_namespace namespace ON namespace.oid=relation.relnamespace
            JOIN pg_proc procedure ON procedure.oid=trigger.tgfoid
           WHERE namespace.nspname='public'
             AND relation.relname=%s
             AND NOT trigger.tgisinternal
             AND (trigger.tgtype & (8 | 32)) <> 0
             AND (
               trigger.tgname ~* '(immutable|append_only|truncate_guard)'
               OR pg_get_functiondef(procedure.oid) ~* '(immutable|append-only)'
             )
        ) AS guarded
        """,
        (table_name,),
    ).fetchone()
    return bool(row and row["guarded"])


def _scoped_count(conn: Any, entry: dict[str, Any], scope: TenantScope) -> int:
    predicate, params = _scope_predicate(entry, scope)
    query = (
        sql.SQL("SELECT COUNT(*) AS count FROM {} WHERE ").format(
            sql.Identifier(str(entry["name"]))
        )
        + predicate
    )
    row = conn.execute(query, params).fetchone()
    return int((row or {}).get("count") or 0)


def build_cleanup_impact_plan(
    conn: Any,
    scope: TenantScope,
    *,
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic, read-only cleanup plan for one exact scope."""
    data = registry or load_tenant_resource_registry()
    issues = validate_registry(data)
    if issues:
        raise ValueError(f"invalid tenant resource registry: {issues}")

    resources: list[dict[str, Any]] = []
    blockers: list[str] = []
    for entry in _business_resources(data):
        name = str(entry["name"])
        if entry.get("kind") != "postgres_table":
            resources.append(
                {
                    "kind": str(entry.get("kind")),
                    "name": name,
                    "strategy": EXTERNAL_NOT_EXECUTED,
                    "rowCount": None,
                    "reason": "external backend requires an explicit probed adapter",
                }
            )
            blockers.append(f"external-not-executed:{entry.get('kind')}:{name}")
            continue
        conn.execute("SAVEPOINT ti6_cleanup_plan_resource")
        try:
            row_count = _scoped_count(conn, entry, scope)
            broader_scope = tuple(entry.get("tenantColumns") or ()) == ("org_id",)
            immutable = (
                False if broader_scope else _has_immutable_delete_guard(conn, name)
            )
        except (psycopg.Error, ValueError) as exc:
            conn.execute("ROLLBACK TO SAVEPOINT ti6_cleanup_plan_resource")
            conn.execute("RELEASE SAVEPOINT ti6_cleanup_plan_resource")
            resources.append(
                {
                    "kind": "postgres_table",
                    "name": name,
                    "strategy": "BLOCKED",
                    "rowCount": None,
                    "reason": f"{type(exc).__name__}: {exc}",
                }
            )
            blockers.append(f"postgres-blocked:{name}")
            continue
        conn.execute("RELEASE SAVEPOINT ti6_cleanup_plan_resource")
        resources.append(
            {
                "kind": "postgres_table",
                "name": name,
                "strategy": (
                    RETAIN_BROADER_SCOPE
                    if broader_scope
                    else RETAIN_IMMUTABLE_HISTORY
                    if immutable
                    else DELETE_SCOPED_ROWS
                ),
                "rowCount": row_count,
                "clearOrder": int(entry.get("clearOrder", 100)),
                "primaryKey": list(entry.get("primaryKey") or ()),
                "tenantColumns": list(entry.get("tenantColumns") or ()),
                "reason": (
                    "organization-scoped data is broader than one workspace"
                    if broader_scope
                    else "database delete/truncate immutability guard"
                    if immutable
                    else "scoped current-state rows"
                ),
            }
        )

    core = {
        "schemaVersion": "aos.dev/tenant-cleanup-impact/v1alpha1",
        "registryVersion": data.get("registryVersion"),
        "orgId": scope.org_id,
        "projectId": scope.project_id,
        "resources": resources,
        "blockers": sorted(blockers),
    }
    return {
        **core,
        "planHash": _canonical_hash(core),
        "postgresRows": sum(
            int(item["rowCount"] or 0)
            for item in resources
            if item["kind"] == "postgres_table"
        ),
        "deletableRows": sum(
            int(item["rowCount"] or 0)
            for item in resources
            if item["strategy"] == DELETE_SCOPED_ROWS
        ),
    }


def _assert_disposable_synthetic_scope(conn: Any, scope: TenantScope) -> str:
    row = conn.execute("SELECT current_database() AS name").fetchone()
    database = str((row or {}).get("name") or "")
    if not database.startswith(_DISPOSABLE_DATABASE_PREFIXES):
        raise PermissionError("cleanup apply requires a disposable TI-6/test database")
    if not (
        scope.org_id.startswith(_SYNTHETIC_PREFIX)
        and scope.project_id.startswith(_SYNTHETIC_PREFIX)
    ):
        raise PermissionError("cleanup apply requires an exact TI-6 synthetic scope")
    return database


def _row_digest(conn: Any, entry: dict[str, Any], scope: TenantScope) -> dict[str, Any]:
    predicate, params = _scope_predicate(entry, scope)
    query = (
        sql.SQL("SELECT to_jsonb(row_value) AS value FROM {} row_value WHERE ").format(
            sql.Identifier(str(entry["name"]))
        )
        + predicate
    )
    rows = conn.execute(query, params).fetchall()
    values = sorted(
        json.dumps(row["value"], ensure_ascii=False, sort_keys=True, default=str)
        for row in rows
    )
    return {"count": len(values), "digest": _canonical_hash(values)}


def _deletion_order(conn: Any, names: set[str]) -> list[str]:
    """Return child-before-parent order for registered scoped tables."""
    if not names:
        return []
    rows = conn.execute(
        """
        SELECT child.relname AS child, parent.relname AS parent
          FROM pg_constraint constraint_row
          JOIN pg_class child ON child.oid=constraint_row.conrelid
          JOIN pg_class parent ON parent.oid=constraint_row.confrelid
          JOIN pg_namespace namespace ON namespace.oid=child.relnamespace
         WHERE constraint_row.contype='f' AND namespace.nspname='public'
        """
    ).fetchall()
    parents: dict[str, set[str]] = defaultdict(set)
    children: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        child, parent = str(row["child"]), str(row["parent"])
        if child in names and parent in names and child != parent:
            parents[child].add(parent)
            children[parent].add(child)

    remaining = set(names)
    ordered: list[str] = []
    while remaining:
        leaves = sorted(name for name in remaining if not (children[name] & remaining))
        if not leaves:
            raise RuntimeError(f"cleanup dependency cycle: {sorted(remaining)}")
        ordered.extend(leaves)
        remaining.difference_update(leaves)
    return ordered


def run_cleanup_rollback_drill(
    conn: Any,
    scope: TenantScope,
    *,
    expected_plan_hash: str,
    peer_scopes: tuple[TenantScope, ...] = (),
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply and verify scoped deletes, then always restore the savepoint."""
    database = _assert_disposable_synthetic_scope(conn, scope)
    data = registry or load_tenant_resource_registry()
    plan = build_cleanup_impact_plan(conn, scope, registry=data)
    if plan["planHash"] != expected_plan_hash:
        raise RuntimeError("cleanup impact plan changed; regenerate dry-run plan")
    blocked_postgres = [
        item
        for item in plan["resources"]
        if item["kind"] == "postgres_table" and item["strategy"] == "BLOCKED"
    ]
    if blocked_postgres:
        raise RuntimeError(
            f"cleanup plan has blocked PostgreSQL resources: {blocked_postgres}"
        )

    entries = {
        str(entry["name"]): entry
        for entry in _business_resources(data)
        if entry.get("kind") == "postgres_table"
    }
    targets = {
        str(item["name"])
        for item in plan["resources"]
        if item["strategy"] == DELETE_SCOPED_ROWS and int(item["rowCount"] or 0) > 0
    }
    before = {name: _row_digest(conn, entries[name], scope) for name in sorted(targets)}
    from aos_api.db import connect

    def peer_digests() -> dict[str, dict[str, dict[str, Any]]]:
        result: dict[str, dict[str, dict[str, Any]]] = {}
        for peer in peer_scopes:
            with connect(peer) as peer_conn:
                result[f"{peer.org_id}/{peer.project_id}"] = {
                    name: _row_digest(peer_conn, entries[name], peer)
                    for name in sorted(targets)
                }
        return result

    peer_before = peer_digests()

    conn.execute("SAVEPOINT ti6_cleanup_drill")
    deleted: dict[str, int] = {}
    try:
        for name in _deletion_order(conn, targets):
            predicate, params = _scope_predicate(entries[name], scope)
            query = (
                sql.SQL("DELETE FROM {} WHERE ").format(sql.Identifier(name))
                + predicate
            )
            cursor = conn.execute(query, params)
            deleted[name] = int(cursor.rowcount or 0)
        after_apply = {
            name: _row_digest(conn, entries[name], scope) for name in sorted(targets)
        }
        if any(item["count"] != 0 for item in after_apply.values()):
            raise AssertionError(f"scoped cleanup verification failed: {after_apply}")
        peer_after_apply = peer_digests()
        if peer_after_apply != peer_before:
            raise AssertionError("cleanup changed peer tenant rows")
    finally:
        conn.execute("ROLLBACK TO SAVEPOINT ti6_cleanup_drill")
        conn.execute("RELEASE SAVEPOINT ti6_cleanup_drill")

    restored = {
        name: _row_digest(conn, entries[name], scope) for name in sorted(targets)
    }
    if restored != before:
        raise AssertionError("cleanup rollback did not restore exact scoped content")
    return {
        "database": database,
        "orgId": scope.org_id,
        "projectId": scope.project_id,
        "planHash": plan["planHash"],
        "deleted": deleted,
        "restored": True,
        "peerScopesUnchanged": True,
    }

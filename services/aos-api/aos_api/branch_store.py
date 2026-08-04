"""89 v2 · Ontology branch overlay — effective view / diff / merge / checkout."""
from __future__ import annotations

import json
from typing import Any

from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope


def ensure_overlay_table(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS obj_branch_overlay (
          branch_id TEXT NOT NULL REFERENCES meta_branch(id) ON DELETE CASCADE,
          object_type TEXT NOT NULL,
          object_id TEXT NOT NULL,
          props JSONB NOT NULL DEFAULT '{}'::jsonb,
          op TEXT NOT NULL DEFAULT 'upsert',
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (branch_id, object_type, object_id)
        )
        """
    )


def get_branch_row(
    conn, branch_id: str, scope: TenantScope | None = None
) -> dict[str, Any] | None:
    if scope is None:
        return conn.execute(
            "SELECT id, name, base_ref, readonly FROM meta_branch WHERE id=%s",
            (branch_id,),
        ).fetchone()
    return conn.execute(
        "SELECT id, name, base_ref, readonly FROM meta_branch "
        "WHERE id=%s AND org_id=%s AND project_id=%s",
        (branch_id, *scope.key),
    ).fetchone()


def is_production_branch(branch_id: str | None, row: dict[str, Any] | None = None) -> bool:
    if not branch_id or branch_id in {"main", "master"}:
        return True
    if row and row.get("readonly"):
        return True
    return False


def _base_props(
    conn,
    object_type: str,
    object_id: str,
    scope: TenantScope | None = None,
) -> dict[str, Any] | None:
    if scope is not None:
        row = conn.execute(
            "SELECT props FROM obj_instance WHERE object_type=%s AND object_id=%s "
            "AND org_id=%s AND project_id=%s",
            (object_type, object_id, *scope.key),
        ).fetchone()
        return dict(row["props"] or {}) if row else None
    row = conn.execute(
        "SELECT props FROM obj_instance WHERE object_type=%s AND object_id=%s",
        (object_type, object_id),
    ).fetchone()
    if not row:
        return None
    return dict(row["props"] or {})


def list_base_objects(conn, object_type: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT object_id, props FROM obj_instance WHERE object_type=%s ORDER BY object_id",
        (object_type,),
    ).fetchall()
    return [{"object_id": r["object_id"], "props": dict(r["props"] or {})} for r in rows]


def list_overlays(
    conn,
    branch_id: str,
    object_type: str | None = None,
    scope: TenantScope | None = None,
) -> list[dict[str, Any]]:
    scope_sql = "" if scope is None else " AND org_id=%s AND project_id=%s"
    scope_params: tuple[str, ...] = () if scope is None else scope.key
    if object_type:
        rows = conn.execute(
            f"""
            SELECT object_type, object_id, props, op FROM obj_branch_overlay
            WHERE branch_id=%s AND object_type=%s{scope_sql}
            ORDER BY object_id
            """,
            (branch_id, object_type, *scope_params),
        ).fetchall()
    else:
        rows = conn.execute(
            f"""
            SELECT object_type, object_id, props, op FROM obj_branch_overlay
            WHERE branch_id=%s{scope_sql}
            ORDER BY object_type, object_id
            """,
            (branch_id, *scope_params),
        ).fetchall()
    return [
        {
            "object_type": r["object_type"],
            "object_id": r["object_id"],
            "props": dict(r["props"] or {}),
            "op": r["op"] or "upsert",
        }
        for r in rows
    ]


def effective_objects(conn, object_type: str, branch_id: str | None) -> list[dict[str, Any]]:
    """Return [{object_id, props}] for the effective branch view."""
    base = list_base_objects(conn, object_type)
    if not branch_id or is_production_branch(branch_id, get_branch_row(conn, branch_id) if branch_id else None):
        return base

    row = get_branch_row(conn, branch_id)
    if not row:
        raise ApiError(code="NOT_FOUND", message=f"branch not found: {branch_id}", status_code=404)
    if row.get("readonly"):
        return base

    overlays = {o["object_id"]: o for o in list_overlays(conn, branch_id, object_type)}
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for b in base:
        oid = b["object_id"]
        seen.add(oid)
        ov = overlays.get(oid)
        if not ov:
            out.append(b)
            continue
        if ov["op"] == "delete":
            continue
        out.append({"object_id": oid, "props": ov["props"]})
    for oid, ov in overlays.items():
        if oid in seen:
            continue
        if ov["op"] == "delete":
            continue
        out.append({"object_id": oid, "props": ov["props"]})
    out.sort(key=lambda x: x["object_id"])
    return out


def effective_object(
    conn, object_type: str, object_id: str, branch_id: str | None
) -> dict[str, Any] | None:
    items = effective_objects(conn, object_type, branch_id)
    for it in items:
        if it["object_id"] == object_id:
            return it
    return None


def upsert_overlay(
    conn,
    scope: TenantScope,
    branch_id: str,
    object_type: str,
    object_id: str,
    props: dict[str, Any],
    op: str = "upsert",
) -> None:
    row = get_branch_row(conn, branch_id, scope)
    if not row:
        raise ApiError(code="NOT_FOUND", message=f"branch not found: {branch_id}", status_code=404)
    if is_production_branch(branch_id, row):
        raise ApiError(
            code="VALIDATION",
            message="production/readonly branch cannot accept overlay writes; use Draft",
            status_code=400,
        )
    if op not in {"upsert", "delete"}:
        raise ApiError(code="VALIDATION", message="op must be upsert|delete", status_code=400)
    result = conn.execute(
        """
        INSERT INTO obj_branch_overlay (
          branch_id, object_type, object_id, props, op, updated_at,
          org_id, project_id
        ) VALUES (%s,%s,%s,%s::jsonb,%s,NOW(),%s,%s)
        ON CONFLICT (branch_id, object_type, object_id) DO UPDATE
          SET props=EXCLUDED.props, op=EXCLUDED.op, updated_at=NOW()
        WHERE obj_branch_overlay.org_id=EXCLUDED.org_id
          AND obj_branch_overlay.project_id=EXCLUDED.project_id
        """,
        (branch_id, object_type, object_id, json.dumps(props or {}), op, *scope.key),
    )
    if result.rowcount == 0:
        raise ApiError(
            code="TENANT_KEY_CONFLICT",
            message="branch overlay key belongs to another tenant or legacy scope",
            status_code=409,
        )


def checkout_object(
    conn,
    scope: TenantScope,
    branch_id: str,
    object_type: str,
    object_id: str,
    patch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = _base_props(conn, object_type, object_id, scope)
    if base is None:
        raise ApiError(code="NOT_FOUND", message="base object not found", status_code=404)
    props = {**base, **(patch or {})}
    upsert_overlay(conn, scope, branch_id, object_type, object_id, props, op="upsert")
    return {"objectType": object_type, "objectId": object_id, "props": props, "op": "upsert"}


def change_count(conn, branch_id: str) -> int:
    row = get_branch_row(conn, branch_id)
    if not row or is_production_branch(branch_id, row):
        return 0
    r = conn.execute(
        "SELECT COUNT(*) AS c FROM obj_branch_overlay WHERE branch_id=%s",
        (branch_id,),
    ).fetchone()
    return int(r["c"] if r else 0)


def diff_branch(conn, branch_id: str) -> dict[str, Any]:
    row = get_branch_row(conn, branch_id)
    if not row:
        raise ApiError(code="NOT_FOUND", message=f"branch not found: {branch_id}", status_code=404)
    base_ref = row["base_ref"] or "main"
    items: list[dict[str, Any]] = []
    for ov in list_overlays(conn, branch_id):
        ot, oid = ov["object_type"], ov["object_id"]
        base = _base_props(conn, ot, oid)
        if ov["op"] == "delete":
            items.append(
                {
                    "objectType": ot,
                    "objectId": oid,
                    "kind": "deleted",
                    "base": base,
                    "branch": None,
                }
            )
            continue
        if base is None:
            items.append(
                {
                    "objectType": ot,
                    "objectId": oid,
                    "kind": "added",
                    "base": None,
                    "branch": ov["props"],
                }
            )
        elif base != ov["props"]:
            items.append(
                {
                    "objectType": ot,
                    "objectId": oid,
                    "kind": "modified",
                    "base": base,
                    "branch": ov["props"],
                }
            )
        else:
            # identical checkout without patch — still a tracked overlay
            items.append(
                {
                    "objectType": ot,
                    "objectId": oid,
                    "kind": "modified",
                    "base": base,
                    "branch": ov["props"],
                }
            )
    return {
        "branchId": branch_id,
        "baseRef": base_ref,
        "items": items,
        "total": len(items),
    }


def merge_branch(
    conn, scope: TenantScope, branch_id: str
) -> dict[str, Any]:
    row = get_branch_row(conn, branch_id, scope)
    if not row:
        raise ApiError(code="NOT_FOUND", message=f"branch not found: {branch_id}", status_code=404)
    if is_production_branch(branch_id, row):
        raise ApiError(code="VALIDATION", message="cannot merge production/readonly branch", status_code=400)
    base_ref = row["base_ref"] or "main"
    # Only support merging into production base for v2
    if base_ref not in {"main", "master"}:
        raise ApiError(
            code="VALIDATION",
            message=f"v2 merge only supports baseRef main/master (got {base_ref})",
            status_code=400,
        )
    overlays = list_overlays(conn, branch_id, scope=scope)
    merged = 0
    for ov in overlays:
        ot, oid = ov["object_type"], ov["object_id"]
        if ov["op"] == "delete":
            conn.execute(
                "DELETE FROM obj_instance WHERE object_type=%s AND object_id=%s "
                "AND org_id=%s AND project_id=%s",
                (ot, oid, *scope.key),
            )
            merged += 1
            continue
        conn.execute(
            """
            INSERT INTO obj_instance (
              object_type, object_id, props, org_id, project_id
            ) VALUES (%s,%s,%s::jsonb,%s,%s)
            ON CONFLICT (object_type, object_id) DO UPDATE SET props=EXCLUDED.props
            WHERE obj_instance.org_id=EXCLUDED.org_id
              AND obj_instance.project_id=EXCLUDED.project_id
            """,
            (ot, oid, json.dumps(ov["props"] or {}), *scope.key),
        )
        merged += 1
    conn.execute(
        "DELETE FROM obj_branch_overlay WHERE branch_id=%s "
        "AND org_id=%s AND project_id=%s",
        (branch_id, *scope.key),
    )
    return {"ok": True, "branchId": branch_id, "baseRef": base_ref, "merged": merged}

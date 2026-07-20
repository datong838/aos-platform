"""TWA.9 / TWA.10 — Organization catalog (PG-backed · 164 v1.1)."""
from __future__ import annotations

import re
from typing import Any

from aos_api import membership as mem
from aos_api import workspaces_catalog as ws_cat
from aos_api.db import connect
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.orgs")

_SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,63}$")
JOIN_POLICIES = frozenset({"invite_or_apply", "invite_only", "closed"})

# org_id -> meta (cache; PG is source of truth across restarts)
_ORGS: dict[str, dict[str, Any]] = {}


def org_count() -> int:
    return len(_ORGS)


def reset_org_store(*, purge_db: bool = False) -> None:
    """Clear in-memory org cache.

    默认 **不** 清 PG：单测与本机共享 aos_meta 时，purge 会误删 org-qyh 等真实组织。
    需要隔离库时显式传 purge_db=True。
    """
    _ORGS.clear()
    if not purge_db:
        return
    try:
        with connect() as conn:
            conn.execute("DELETE FROM meta_org")
            conn.commit()
    except Exception:  # noqa: BLE001 — tests may run before schema
        log.debug("org_store_purge_skip", exc_info=True)


def _persist_org(row: dict[str, Any]) -> None:
    try:
        from aos_api.tenant_catalog import ensure_tenant_catalog_schema

        ensure_tenant_catalog_schema()
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO meta_org (id, name, kind, join_policy, discoverable, updated_at)
                VALUES (%s,%s,%s,%s,%s,NOW())
                ON CONFLICT (id) DO UPDATE SET
                  name=EXCLUDED.name,
                  kind=EXCLUDED.kind,
                  join_policy=EXCLUDED.join_policy,
                  discoverable=EXCLUDED.discoverable,
                  updated_at=NOW()
                """,
                (
                    row["id"],
                    row["name"],
                    row.get("kind") or "standard",
                    row.get("joinPolicy") or "invite_or_apply",
                    bool(row.get("discoverable", True)),
                ),
            )
            conn.commit()
    except Exception:  # noqa: BLE001
        log.warning("org_persist_fail id=%s", row.get("id"), exc_info=True)


def _delete_org_db(org_id: str) -> None:
    try:
        with connect() as conn:
            conn.execute("DELETE FROM meta_org WHERE id=%s", (org_id,))
            conn.commit()
    except Exception:  # noqa: BLE001
        log.warning("org_delete_fail id=%s", org_id, exc_info=True)


def load_orgs_from_db() -> int:
    _ORGS.clear()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT id, name, kind, join_policy, discoverable FROM meta_org ORDER BY id"
            ).fetchall()
    except Exception:  # noqa: BLE001
        log.warning("org_load_fail", exc_info=True)
        return 0
    for r in rows:
        _ORGS[str(r["id"])] = {
            "id": str(r["id"]),
            "name": str(r["name"]),
            "kind": str(r["kind"] or "standard"),
            "joinPolicy": str(r["join_policy"] or "invite_or_apply"),
            "discoverable": bool(r["discoverable"]),
        }
    log.info("org_load count=%s", len(_ORGS))
    return len(_ORGS)


def seed_dev_orgs() -> None:
    """Upsert Dev seed orgs only if missing (never wipe user orgs).

    164+：不再种子 org-a / org-b（演示组织已废止；产品面仅留默认组织 + 用户自建）。
    """
    if "dev-org" not in _ORGS:
        ensure_org(
            "dev-org",
            name="默认组织",
            kind="standard",
            join_policy="invite_or_apply",
            discoverable=True,
        )


def ensure_org(
    org_id: str,
    *,
    name: str | None = None,
    kind: str = "standard",
    join_policy: str = "invite_or_apply",
    discoverable: bool = True,
) -> dict[str, Any]:
    if org_id not in _ORGS:
        policy = join_policy if join_policy in JOIN_POLICIES else "invite_or_apply"
        _ORGS[org_id] = {
            "id": org_id,
            "name": name or org_id,
            "kind": kind,
            "joinPolicy": policy,
            "discoverable": discoverable,
        }
        _persist_org(_ORGS[org_id])
    else:
        changed = False
        if name and _ORGS[org_id].get("name") != name:
            _ORGS[org_id]["name"] = name
            changed = True
        if kind and _ORGS[org_id].get("kind") != kind:
            _ORGS[org_id]["kind"] = kind
            changed = True
        if join_policy in JOIN_POLICIES and _ORGS[org_id].get("joinPolicy") != join_policy:
            _ORGS[org_id]["joinPolicy"] = join_policy
            changed = True
        if changed:
            _persist_org(_ORGS[org_id])
    return dict(_ORGS[org_id])


def get_org(org_id: str) -> dict[str, Any] | None:
    row = _ORGS.get(org_id)
    return dict(row) if row else None


def list_orgs_for_subject(subject: str) -> list[dict[str, Any]]:
    """Orgs where subject has ≥1 workspace membership."""
    out: list[dict[str, Any]] = []
    for oid in sorted(mem.member_org_ids(subject)):
        ensure_org(oid)
        out.append(dict(_ORGS[oid]))
    return out


def list_directory(subject: str) -> list[dict[str, Any]]:
    """Discoverable orgs for join UX (TWA.10)."""
    member = mem.member_org_ids(subject)
    out: list[dict[str, Any]] = []
    for oid, row in sorted(_ORGS.items()):
        if not row.get("discoverable", True):
            continue
        item = dict(row)
        item["member"] = oid in member
        out.append(item)
    return out


def create_org(
    *,
    name: str,
    org_id: str | None = None,
    join_policy: str = "invite_or_apply",
    actor_id: str,
) -> dict[str, Any]:
    display = (name or "").strip()
    if not display:
        raise ValueError("name required")
    oid = (org_id or "").strip()
    if not oid:
        slug = re.sub(r"[^A-Za-z0-9._-]+", "-", display.lower()).strip("-")
        slug = slug[:40] or "org"
        oid = f"org-{slug}"
        n = 0
        while oid in _ORGS:
            n += 1
            oid = f"org-{slug}-{n}"
    if not _SAFE.match(oid):
        raise ValueError("orgId must be 2-64 chars [A-Za-z0-9._-]")
    if oid in _ORGS:
        raise ValueError("organization already exists")
    policy = join_policy if join_policy in JOIN_POLICIES else "invite_or_apply"
    org = ensure_org(
        oid,
        name=display,
        kind="standard",
        join_policy=policy,
        discoverable=True,
    )
    default_project = "dev-project"
    ws_cat.ensure_workspace(
        oid,
        default_project,
        name="默认工作区",
        deletable=True,
        kind="default",
    )
    mem.upsert_member(
        oid,
        default_project,
        actor_id,
        "owner",
        actor_id=actor_id,
    )
    mem.append_audit(
        org_id=oid,
        project_id=default_project,
        actor_id=actor_id,
        action="org.create",
        detail={"name": display, "joinPolicy": policy},
    )
    log.info("org_create id=%s name=%s actor=%s", oid, display, actor_id)
    return {
        **org,
        "defaultProjectId": default_project,
        "workspaceName": "默认工作区",
    }


def remove_org(org_id: str) -> bool:
    if org_id not in _ORGS:
        return False
    del _ORGS[org_id]
    _delete_org_db(org_id)
    log.info("org_remove id=%s", org_id)
    return True


def default_project_for_org(org_id: str, subject: str) -> str | None:
    projects = mem.member_project_ids(org_id, subject)
    if not projects:
        return None
    if "dev-project" in projects:
        return "dev-project"
    if "qyh-test" in projects:
        return "qyh-test"
    return sorted(projects)[0]


def org_name(org_id: str) -> str:
    ensure_org(org_id)
    return str(_ORGS[org_id].get("name") or org_id)


def workspace_display_name(org_id: str, project_id: str) -> str:
    ws = ws_cat.get_workspace(org_id, project_id)
    if ws:
        return str(ws["name"])
    if project_id in ("dev-project", "test-workspace", "qyh-test"):
        return "测试工作区"
    return project_id

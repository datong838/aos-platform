"""TWA.9 / TWA.10 — Organization catalog (P3 multi-org; in-memory)."""
from __future__ import annotations

import re
from typing import Any

from aos_api import membership as mem
from aos_api import workspaces_catalog as ws_cat
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.orgs")

_SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,63}$")
JOIN_POLICIES = frozenset({"invite_or_apply", "invite_only", "closed"})

# org_id -> meta
_ORGS: dict[str, dict[str, Any]] = {}


def reset_org_store() -> None:
    _ORGS.clear()


def seed_dev_orgs() -> None:
    for oid, name, kind in (
        ("dev-org", "默认组织", "standard"),
        ("org-a", "组织 A", "group"),
        ("org-b", "组织 B", "group"),
    ):
        _ORGS[oid] = {
            "id": oid,
            "name": name,
            "kind": kind,
            "joinPolicy": "invite_or_apply",
            "discoverable": True,
        }


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
    else:
        if name:
            _ORGS[org_id]["name"] = name
        if kind:
            _ORGS[org_id]["kind"] = kind
        if join_policy in JOIN_POLICIES:
            _ORGS[org_id]["joinPolicy"] = join_policy
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
    log.info("org_remove id=%s", org_id)
    return True


def default_project_for_org(org_id: str, subject: str) -> str | None:
    projects = mem.member_project_ids(org_id, subject)
    if not projects:
        return None
    # Prefer 测试/默认工作区 if present
    if "dev-project" in projects:
        return "dev-project"
    return sorted(projects)[0]


def org_name(org_id: str) -> str:
    ensure_org(org_id)
    return str(_ORGS[org_id].get("name") or org_id)


def workspace_display_name(org_id: str, project_id: str) -> str:
    ws = ws_cat.get_workspace(org_id, project_id)
    if ws:
        return str(ws["name"])
    if project_id in ("dev-project", "test-workspace"):
        return "测试工作区"
    return project_id


# bootstrap
seed_dev_orgs()

"""TWA.9 — Organization catalog (P3 multi-org; in-memory)."""
from __future__ import annotations

from typing import Any

from aos_api import membership as mem
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.orgs")

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
        }


def ensure_org(org_id: str, *, name: str | None = None, kind: str = "standard") -> dict[str, Any]:
    if org_id not in _ORGS:
        _ORGS[org_id] = {
            "id": org_id,
            "name": name or org_id,
            "kind": kind,
        }
    elif name:
        _ORGS[org_id]["name"] = name
        if kind:
            _ORGS[org_id]["kind"] = kind
    return _ORGS[org_id]


def get_org(org_id: str) -> dict[str, Any] | None:
    return _ORGS.get(org_id)


def list_orgs_for_subject(subject: str) -> list[dict[str, Any]]:
    """Orgs where subject has ≥1 workspace membership."""
    out: list[dict[str, Any]] = []
    for oid in sorted(mem.member_org_ids(subject)):
        ensure_org(oid)
        out.append(dict(_ORGS[oid]))
    return out


def default_project_for_org(org_id: str, subject: str) -> str | None:
    projects = mem.member_project_ids(org_id, subject)
    if not projects:
        return None
    # Prefer 测试工作区 if present
    if "dev-project" in projects:
        return "dev-project"
    return sorted(projects)[0]


def org_name(org_id: str) -> str:
    ensure_org(org_id)
    return str(_ORGS[org_id].get("name") or org_id)


# bootstrap
seed_dev_orgs()

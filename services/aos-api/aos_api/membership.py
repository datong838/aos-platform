"""TWA.7 — in-memory membership + audit (no PG)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from aos_api.logging_facade import get_logger

log = get_logger("aos-api.membership")

Role = Literal["owner", "admin", "editor", "viewer"]
ROLES: set[str] = {"owner", "admin", "editor", "viewer"}
ADMIN_ROLES: set[str] = {"owner", "admin"}

# (org_id, project_id, subject) -> role
_MEMBERS: dict[tuple[str, str, str], str] = {}
_AUDIT: list[dict[str, Any]] = []


def reset_membership_store() -> None:
    _MEMBERS.clear()
    _AUDIT.clear()


def seed_dev_defaults() -> None:
    for org in ("dev-org", "org-a", "org-b"):
        for project, sub, role in (
            ("dev-project", "alice", "owner"),
            ("prj-ops", "alice", "owner"),
            ("prj-1", "alice", "owner"),
            ("prj-2", "alice", "owner"),
            ("dev-project", "user:dev", "owner"),
            ("prj-ops", "user:dev", "owner"),
            ("prj-1", "user:dev", "owner"),
            ("prj-2", "user:dev", "owner"),
            ("prj-ops", "bob", "viewer"),
        ):
            _MEMBERS[(org, project, sub)] = role


def ensure_default_membership(org_id: str, project_id: str, subject: str) -> None:
    """If subject has no membership anywhere in org, grant owner on current project."""
    if member_project_ids(org_id, subject):
        return
    _MEMBERS[(org_id, project_id, subject)] = "owner"
    append_audit(
        org_id=org_id,
        project_id=project_id,
        actor_id=subject,
        action="membership.bootstrap",
        detail={"subject": subject, "role": "owner"},
    )
    log.info(
        "membership_bootstrap org=%s project=%s subject=%s",
        org_id,
        project_id,
        subject,
    )


def list_members(org_id: str, project_id: str) -> list[dict[str, Any]]:
    return [
        {
            "subject": sub,
            "role": role,
            "orgId": org_id,
            "projectId": project_id,
        }
        for (o, p, sub), role in sorted(_MEMBERS.items())
        if o == org_id and p == project_id
    ]


def get_role(org_id: str, project_id: str, subject: str) -> str | None:
    return _MEMBERS.get((org_id, project_id, subject))


def is_member(org_id: str, project_id: str, subject: str) -> bool:
    return get_role(org_id, project_id, subject) is not None


def can_manage_members(org_id: str, project_id: str, subject: str) -> bool:
    role = get_role(org_id, project_id, subject)
    return role in ADMIN_ROLES if role else False


def upsert_member(
    org_id: str,
    project_id: str,
    subject: str,
    role: str,
    *,
    actor_id: str,
) -> dict[str, Any]:
    if role not in ROLES:
        raise ValueError(f"invalid role {role}")
    _MEMBERS[(org_id, project_id, subject)] = role
    row = {
        "subject": subject,
        "role": role,
        "orgId": org_id,
        "projectId": project_id,
    }
    append_audit(
        org_id=org_id,
        project_id=project_id,
        actor_id=actor_id,
        action="membership.upsert",
        detail={"subject": subject, "role": role},
    )
    log.info(
        "membership_upsert org=%s project=%s subject=%s role=%s actor=%s",
        org_id,
        project_id,
        subject,
        role,
        actor_id,
    )
    return row


def remove_member(
    org_id: str,
    project_id: str,
    subject: str,
    *,
    actor_id: str,
) -> bool:
    key = (org_id, project_id, subject)
    if key not in _MEMBERS:
        return False
    del _MEMBERS[key]
    append_audit(
        org_id=org_id,
        project_id=project_id,
        actor_id=actor_id,
        action="membership.remove",
        detail={"subject": subject},
    )
    log.info(
        "membership_remove org=%s project=%s subject=%s actor=%s",
        org_id,
        project_id,
        subject,
        actor_id,
    )
    return True


def member_project_ids(org_id: str, subject: str) -> set[str]:
    return {p for (o, p, s), _ in _MEMBERS.items() if o == org_id and s == subject}


def member_org_ids(subject: str) -> set[str]:
    return {o for (o, _p, s), _ in _MEMBERS.items() if s == subject}


def append_audit(
    *,
    org_id: str,
    project_id: str,
    actor_id: str,
    action: str,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "id": f"aud-{len(_AUDIT) + 1}",
        "ts": datetime.now(timezone.utc).isoformat(),
        "orgId": org_id,
        "projectId": project_id,
        "actorId": actor_id,
        "action": action,
        "detail": detail or {},
    }
    _AUDIT.append(row)
    log.info(
        "audit_append id=%s action=%s org=%s project=%s actor=%s",
        row["id"],
        action,
        org_id,
        project_id,
        actor_id,
    )
    return row


def list_audit(
    org_id: str, project_id: str, *, limit: int = 50
) -> list[dict[str, Any]]:
    rows = [
        r
        for r in reversed(_AUDIT)
        if r["orgId"] == org_id and r["projectId"] == project_id
    ]
    return rows[:limit]


seed_dev_defaults()

"""TWA.7 — membership + audit (memory + optional PG 181m)."""
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
    from aos_api import twa_pg

    twa_pg.truncate_members()


def seed_dev_defaults() -> None:
    from aos_api.person_identity import reset_person_store, seed_dev_persons

    reset_person_store()
    seed_dev_persons()
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
            upsert_member(org, project, sub, role, actor_id="system:seed", _silent=True)


def ensure_default_membership(org_id: str, project_id: str, subject: str) -> None:
    """If subject has no membership anywhere in org, grant owner on current project."""
    if member_project_ids(org_id, subject):
        return
    _MEMBERS[(org_id, project_id, subject)] = "owner"
    from aos_api import twa_pg

    twa_pg.upsert_member(org_id, project_id, subject, "owner")
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


def can_manage_org(org_id: str, subject: str) -> bool:
    """Org admin if owner/admin on any workspace in the org (TWA.10)."""
    for (o, _p, s), role in _MEMBERS.items():
        if o == org_id and s == subject and role in ADMIN_ROLES:
            return True
    return False


def upsert_member(
    org_id: str,
    project_id: str,
    subject: str,
    role: str,
    *,
    actor_id: str,
    _silent: bool = False,
) -> dict[str, Any]:
    if role not in ROLES:
        raise ValueError(f"invalid role {role}")
    _MEMBERS[(org_id, project_id, subject)] = role
    from aos_api import twa_pg

    twa_pg.upsert_member(org_id, project_id, subject, role)
    row = {
        "subject": subject,
        "role": role,
        "orgId": org_id,
        "projectId": project_id,
    }
    if not _silent:
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
    from aos_api import twa_pg

    twa_pg.delete_member(org_id, project_id, subject)
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


def project_ids_for_org(org_id: str) -> set[str]:
    return {p for (o, p, _s) in _MEMBERS if o == org_id}


def remove_all_members_for_project(
    org_id: str, project_id: str, *, actor_id: str
) -> int:
    keys = [(o, p, s) for (o, p, s) in list(_MEMBERS) if o == org_id and p == project_id]
    for key in keys:
        del _MEMBERS[key]
    from aos_api import twa_pg

    twa_pg.delete_members_for_project(org_id, project_id)
    if keys:
        append_audit(
            org_id=org_id,
            project_id=project_id,
            actor_id=actor_id,
            action="membership.clear_project",
            detail={"removed": len(keys)},
        )
    return len(keys)


def remove_all_members_for_org(org_id: str, *, actor_id: str) -> int:
    keys = [(o, p, s) for (o, p, s) in list(_MEMBERS) if o == org_id]
    for key in keys:
        del _MEMBERS[key]
    from aos_api import twa_pg

    twa_pg.delete_members_for_org(org_id)
    if keys:
        append_audit(
            org_id=org_id,
            project_id="-",
            actor_id=actor_id,
            action="membership.clear_org",
            detail={"removed": len(keys)},
        )
    return len(keys)


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
    from aos_api import twa_pg

    twa_pg.append_audit(row)
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

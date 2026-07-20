"""TWA.7 — membership + audit (membership PG-backed · 164 v1.1; audit still memory)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from aos_api.db import connect
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.membership")

Role = Literal["owner", "admin", "editor", "viewer"]
ROLES: set[str] = {"owner", "admin", "editor", "viewer"}
ADMIN_ROLES: set[str] = {"owner", "admin"}

# (org_id, project_id, subject) -> role
_MEMBERS: dict[tuple[str, str, str], str] = {}
_AUDIT: list[dict[str, Any]] = []


def membership_count() -> int:
    return len(_MEMBERS)


def reset_membership_store(*, purge_db: bool = False) -> None:
    """Clear in-memory membership; 默认不清 meta_membership（避免单测误删真实租户成员）。"""
    import os

    _MEMBERS.clear()
    _AUDIT.clear()
    from aos_api import twa_pg

    if (os.getenv("AOS_TWA_STORE") or "").strip().lower() == "pg":
        twa_pg.truncate_members()
    if not purge_db:
        return
    try:
        with connect() as conn:
            conn.execute("DELETE FROM meta_membership")
            conn.commit()
    except Exception:  # noqa: BLE001
        log.debug("membership_purge_skip", exc_info=True)


def _persist_member(org_id: str, project_id: str, subject: str, role: str) -> None:
    try:
        from aos_api.tenant_catalog import ensure_tenant_catalog_schema

        ensure_tenant_catalog_schema()
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO meta_membership (org_id, project_id, subject, role, updated_at)
                VALUES (%s,%s,%s,%s,NOW())
                ON CONFLICT (org_id, project_id, subject) DO UPDATE SET
                  role=EXCLUDED.role,
                  updated_at=NOW()
                """,
                (org_id, project_id, subject, role),
            )
            conn.commit()
    except Exception:  # noqa: BLE001
        log.warning(
            "membership_persist_fail org=%s project=%s subject=%s",
            org_id,
            project_id,
            subject,
            exc_info=True,
        )
    try:
        from aos_api import twa_pg

        twa_pg.upsert_member(org_id, project_id, subject, role)
    except Exception:  # noqa: BLE001
        log.debug("membership_twa_dual_write_skip", exc_info=True)


def _delete_member_db(org_id: str, project_id: str, subject: str) -> None:
    try:
        with connect() as conn:
            conn.execute(
                """
                DELETE FROM meta_membership
                WHERE org_id=%s AND project_id=%s AND subject=%s
                """,
                (org_id, project_id, subject),
            )
            conn.commit()
    except Exception:  # noqa: BLE001
        log.warning(
            "membership_delete_fail org=%s project=%s subject=%s",
            org_id,
            project_id,
            subject,
            exc_info=True,
        )
    try:
        from aos_api import twa_pg

        twa_pg.delete_member(org_id, project_id, subject)
    except Exception:  # noqa: BLE001
        log.debug("membership_twa_delete_skip", exc_info=True)


def load_memberships_from_db() -> int:
    _MEMBERS.clear()
    try:
        with connect() as conn:
            rows = conn.execute(
                """
                SELECT org_id, project_id, subject, role
                FROM meta_membership
                ORDER BY org_id, project_id, subject
                """
            ).fetchall()
    except Exception:  # noqa: BLE001
        log.warning("membership_load_fail", exc_info=True)
        return 0
    for r in rows:
        _MEMBERS[(str(r["org_id"]), str(r["project_id"]), str(r["subject"]))] = str(r["role"])
    log.info("membership_load count=%s", len(_MEMBERS))
    return len(_MEMBERS)


def seed_dev_defaults(*, reset_persons: bool = True) -> None:
    """Upsert Dev seed memberships; does not wipe user-created org members."""
    from aos_api.person_identity import reset_person_store, seed_dev_persons

    if reset_persons:
        reset_person_store()
        seed_dev_persons()
    # 仅默认组织成员种子；不再为 org-a/org-b 播种
    org = "dev-org"
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
        key = (org, project, sub)
        if key in _MEMBERS:
            continue
        _MEMBERS[key] = role
        _persist_member(org, project, sub, role)


def ensure_default_membership(org_id: str, project_id: str, subject: str) -> None:
    """If subject has no membership anywhere in org, grant owner on current project."""
    if member_project_ids(org_id, subject):
        return
    _MEMBERS[(org_id, project_id, subject)] = "owner"
    _persist_member(org_id, project_id, subject, "owner")
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
) -> dict[str, Any]:
    if role not in ROLES:
        raise ValueError(f"invalid role {role}")
    _MEMBERS[(org_id, project_id, subject)] = role
    _persist_member(org_id, project_id, subject, role)
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
    _delete_member_db(org_id, project_id, subject)
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
        _delete_member_db(key[0], key[1], key[2])
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
        _delete_member_db(key[0], key[1], key[2])
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
    try:
        from aos_api import twa_pg

        twa_pg.append_audit(row)
    except Exception:  # noqa: BLE001
        log.debug("audit_twa_dual_write_skip", exc_info=True)
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

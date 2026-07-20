"""TWA.10 — org invite tokens + join requests (in-memory)."""
from __future__ import annotations

import secrets
import time
from typing import Any, Literal

from aos_api import membership as mem
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.org-invites")

Decision = Literal["approve", "reject"]

# token -> invite
_INVITES: dict[str, dict[str, Any]] = {}
# id -> join request
_JOIN_REQS: dict[str, dict[str, Any]] = {}
_JR_SEQ = 0


def reset_org_invites_store() -> None:
    global _JR_SEQ
    _INVITES.clear()
    _JOIN_REQS.clear()
    _JR_SEQ = 0
    from aos_api import twa_pg

    twa_pg.truncate_invites()


def clear_org_artifacts(org_id: str) -> dict[str, int]:
    inv = [t for t, r in list(_INVITES.items()) if r.get("orgId") == org_id]
    for t in inv:
        del _INVITES[t]
    jr = [i for i, r in list(_JOIN_REQS.items()) if r.get("orgId") == org_id]
    for i in jr:
        del _JOIN_REQS[i]
    from aos_api import twa_pg

    twa_pg.delete_invites_for_org(org_id)
    return {"invites": len(inv), "joinRequests": len(jr)}


def create_invite(
    *,
    org_id: str,
    actor_id: str,
    role: str = "viewer",
    project_id: str = "dev-project",
    max_uses: int = 10,
    ttl_hours: int = 168,
) -> dict[str, Any]:
    if role not in mem.ROLES:
        raise ValueError("invalid role")
    token = secrets.token_urlsafe(18)
    now = time.time()
    row = {
        "token": token,
        "orgId": org_id,
        "projectId": project_id,
        "role": role,
        "maxUses": max(1, int(max_uses)),
        "uses": 0,
        "createdBy": actor_id,
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "expiresAt": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(now + max(1, int(ttl_hours)) * 3600)
        ),
        "_expiresTs": now + max(1, int(ttl_hours)) * 3600,
        "status": "active",
    }
    _INVITES[token] = row
    from aos_api import twa_pg

    twa_pg.upsert_invite(row)
    mem.append_audit(
        org_id=org_id,
        project_id=project_id,
        actor_id=actor_id,
        action="org.invite_create",
        detail={"tokenSuffix": token[-6:], "role": role, "maxUses": row["maxUses"]},
    )
    log.info(
        "org_invite_create org=%s project=%s role=%s actor=%s",
        org_id,
        project_id,
        role,
        actor_id,
    )
    return public_invite(row)


def public_invite(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "token": row["token"],
        "orgId": row["orgId"],
        "projectId": row["projectId"],
        "role": row["role"],
        "maxUses": row["maxUses"],
        "uses": row["uses"],
        "createdBy": row["createdBy"],
        "createdAt": row["createdAt"],
        "expiresAt": row["expiresAt"],
        "status": row["status"],
        "invitePath": f"/org/invite/{row['token']}",
    }


def get_invite(token: str) -> dict[str, Any] | None:
    row = _INVITES.get(token)
    if not row:
        return None
    if row["status"] != "active":
        return dict(row)
    if time.time() > float(row.get("_expiresTs", 0)):
        row["status"] = "expired"
        from aos_api import twa_pg

        twa_pg.upsert_invite(row)
    if int(row["uses"]) >= int(row["maxUses"]):
        row["status"] = "exhausted"
        from aos_api import twa_pg

        twa_pg.upsert_invite(row)
    return dict(row)


def accept_invite(*, token: str, subject: str) -> dict[str, Any]:
    row = get_invite(token)
    if not row or row.get("status") != "active":
        raise LookupError("invite not available")
    stored = _INVITES[token]
    if mem.is_member(stored["orgId"], stored["projectId"], subject):
        # already member — still count as success, no double-use increment needed for idempotency
        return {
            "orgId": stored["orgId"],
            "projectId": stored["projectId"],
            "role": mem.get_role(stored["orgId"], stored["projectId"], subject),
            "alreadyMember": True,
        }
    mem.upsert_member(
        stored["orgId"],
        stored["projectId"],
        subject,
        stored["role"],
        actor_id=subject,
    )
    stored["uses"] = int(stored["uses"]) + 1
    if int(stored["uses"]) >= int(stored["maxUses"]):
        stored["status"] = "exhausted"
    from aos_api import twa_pg

    twa_pg.upsert_invite(stored)
    mem.append_audit(
        org_id=stored["orgId"],
        project_id=stored["projectId"],
        actor_id=subject,
        action="org.invite_accept",
        detail={"tokenSuffix": token[-6:], "role": stored["role"]},
    )
    log.info(
        "org_invite_accept org=%s project=%s subject=%s",
        stored["orgId"],
        stored["projectId"],
        subject,
    )
    return {
        "orgId": stored["orgId"],
        "projectId": stored["projectId"],
        "role": stored["role"],
        "alreadyMember": False,
    }


def create_join_request(
    *,
    org_id: str,
    subject: str,
    message: str = "",
    project_id: str = "dev-project",
) -> dict[str, Any]:
    global _JR_SEQ
    # dedupe pending
    for r in _JOIN_REQS.values():
        if (
            r["orgId"] == org_id
            and r["subject"] == subject
            and r["status"] == "pending"
        ):
            return dict(r)
    _JR_SEQ += 1
    rid = f"jr-{_JR_SEQ}"
    row = {
        "id": rid,
        "orgId": org_id,
        "projectId": project_id,
        "subject": subject,
        "message": (message or "").strip()[:500],
        "status": "pending",
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "decidedBy": None,
        "decidedAt": None,
    }
    _JOIN_REQS[rid] = row
    from aos_api import twa_pg

    twa_pg.upsert_join_request(row)
    mem.append_audit(
        org_id=org_id,
        project_id=project_id,
        actor_id=subject,
        action="org.join_request",
        detail={"requestId": rid},
    )
    log.info("org_join_request org=%s subject=%s id=%s", org_id, subject, rid)
    return dict(row)


def list_join_requests(org_id: str, *, status: str | None = "pending") -> list[dict[str, Any]]:
    rows = [dict(r) for r in _JOIN_REQS.values() if r["orgId"] == org_id]
    if status:
        rows = [r for r in rows if r["status"] == status]
    return sorted(rows, key=lambda x: x["createdAt"], reverse=True)


def decide_join_request(
    *,
    org_id: str,
    request_id: str,
    decision: Decision,
    actor_id: str,
    role: str = "viewer",
    project_id: str | None = None,
) -> dict[str, Any]:
    row = _JOIN_REQS.get(request_id)
    if not row or row["orgId"] != org_id:
        raise LookupError("join request not found")
    if row["status"] != "pending":
        raise ValueError("join request already decided")
    if decision not in ("approve", "reject"):
        raise ValueError("invalid decision")
    if role not in mem.ROLES:
        raise ValueError("invalid role")
    pid = project_id or row["projectId"]
    row["status"] = "approved" if decision == "approve" else "rejected"
    row["decidedBy"] = actor_id
    row["decidedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    row["projectId"] = pid
    from aos_api import twa_pg

    twa_pg.upsert_join_request(row)
    if decision == "approve":
        mem.upsert_member(org_id, pid, row["subject"], role, actor_id=actor_id)
        mem.append_audit(
            org_id=org_id,
            project_id=pid,
            actor_id=actor_id,
            action="org.join_approve",
            detail={"requestId": request_id, "subject": row["subject"], "role": role},
        )
    else:
        mem.append_audit(
            org_id=org_id,
            project_id=pid,
            actor_id=actor_id,
            action="org.join_reject",
            detail={"requestId": request_id, "subject": row["subject"]},
        )
    log.info(
        "org_join_decide id=%s decision=%s org=%s subject=%s actor=%s",
        request_id,
        decision,
        org_id,
        row["subject"],
        actor_id,
    )
    return dict(row)

"""Role-separated, reversible TI-1 E3 authz backfill execution."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from aos_api.tenant_dual_write import stable_key_hash


def authz_content_hash(row: Mapping[str, Any], org_id: str = "", project_id: str = "") -> str:
    return stable_key_hash(
        "authz_tuple",
        str(row["user_key"]),
        str(row["relation"]),
        str(row["object_key"]),
        org_id,
        project_id,
    )


def approve_batch(
    conn: Any,
    *,
    owner_org_id: str,
    owner_project_id: str,
    batch_id: str,
    approver_actor_hash: str,
    evidence_hash: str,
) -> dict[str, Any]:
    _lock_batch(conn, batch_id)
    planner_hashes = _actor_hashes(
        conn, owner_org_id, owner_project_id, batch_id, "PLANNED"
    )
    if not planner_hashes:
        raise RuntimeError("batch has no PLANNED event")
    if approver_actor_hash in planner_hashes:
        raise RuntimeError("planner and approver must be different actors")
    inserted = _append_batch_event(
        conn,
        owner_org_id=owner_org_id,
        owner_project_id=owner_project_id,
        batch_id=batch_id,
        status="APPROVED",
        evidence_hash=evidence_hash,
        actor_role="APPROVER",
        actor_hash=approver_actor_hash,
    )
    return {"batchId": batch_id, "approved": True, "replayed": not inserted}


def apply_batch(
    conn: Any,
    *,
    owner_org_id: str,
    owner_project_id: str,
    batch_id: str,
    executor_actor_hash: str,
) -> dict[str, Any]:
    _lock_batch(conn, batch_id)
    approver_hashes = _actor_hashes(
        conn, owner_org_id, owner_project_id, batch_id, "APPROVED"
    )
    if not approver_hashes:
        raise RuntimeError("batch is not approved")
    if executor_actor_hash in approver_hashes:
        raise RuntimeError("approver and executor must be different actors")
    if _batch_has_status(conn, owner_org_id, owner_project_id, batch_id, "COMPLETED"):
        return {"batchId": batch_id, "applied": 0, "replayed": True}

    decisions = _assign_decisions(conn, owner_org_id, owner_project_id, batch_id)
    candidates = _unassigned_authz_rows(conn)
    indexed = {
        stable_key_hash(
            "authz_tuple",
            str(row["user_key"]),
            str(row["relation"]),
            str(row["object_key"]),
        ): row
        for row in candidates
    }
    prepared: list[tuple[Mapping[str, Any], Mapping[str, Any], str]] = []
    conflicts: list[Mapping[str, Any]] = []
    for decision in decisions:
        row = indexed.get(str(decision["key_hash"]))
        if row is None:
            conflicts.append(decision)
            continue
        before_hash = authz_content_hash(row)
        if before_hash != str(decision["before_hash"]):
            conflicts.append(decision)
            continue
        prepared.append((decision, row, before_hash))
    if conflicts:
        for decision in conflicts:
            _append_decision_event(
                conn,
                owner_org_id=owner_org_id,
                owner_project_id=owner_project_id,
                batch_id=batch_id,
                decision=decision,
                event_type="CONFLICT",
                before_hash=str(decision["before_hash"]),
                after_hash=None,
                actor_role="EXECUTOR",
                actor_hash=executor_actor_hash,
            )
        return {
            "batchId": batch_id,
            "gate": "BLOCKED",
            "conflicts": len(conflicts),
            "applied": 0,
        }

    _append_batch_event(
        conn,
        owner_org_id=owner_org_id,
        owner_project_id=owner_project_id,
        batch_id=batch_id,
        status="EXECUTING",
        evidence_hash=stable_key_hash(batch_id, "EXECUTING", str(len(prepared))),
        actor_role="EXECUTOR",
        actor_hash=executor_actor_hash,
    )
    for decision, row, before_hash in prepared:
        target_org_id = str(decision["target_org_id"])
        target_project_id = str(decision["target_project_id"])
        updated = conn.execute(
            """
            UPDATE authz_tuple
               SET org_id=%s, project_id=%s
             WHERE user_key=%s AND relation=%s AND object_key=%s
               AND org_id IS NULL AND project_id IS NULL
            RETURNING user_key
            """,
            (
                target_org_id,
                target_project_id,
                row["user_key"],
                row["relation"],
                row["object_key"],
            ),
        ).fetchone()
        if not updated:
            raise RuntimeError("authz row changed during E3 apply")
        after_hash = authz_content_hash(row, target_org_id, target_project_id)
        _append_decision_event(
            conn,
            owner_org_id=owner_org_id,
            owner_project_id=owner_project_id,
            batch_id=batch_id,
            decision=decision,
            event_type="APPLIED",
            before_hash=before_hash,
            after_hash=after_hash,
            actor_role="EXECUTOR",
            actor_hash=executor_actor_hash,
        )
    _append_batch_event(
        conn,
        owner_org_id=owner_org_id,
        owner_project_id=owner_project_id,
        batch_id=batch_id,
        status="COMPLETED",
        evidence_hash=stable_key_hash(batch_id, "COMPLETED", str(len(prepared))),
        actor_role="EXECUTOR",
        actor_hash=executor_actor_hash,
    )
    return {
        "batchId": batch_id,
        "gate": "GREEN",
        "applied": len(prepared),
        "replayed": False,
    }


def verify_batch(
    conn: Any,
    *,
    owner_org_id: str,
    owner_project_id: str,
    batch_id: str,
    verifier_actor_hash: str,
) -> dict[str, Any]:
    _lock_batch(conn, batch_id)
    forbidden = _actor_hashes(
        conn, owner_org_id, owner_project_id, batch_id, "APPROVED"
    ) | _actor_hashes(conn, owner_org_id, owner_project_id, batch_id, "COMPLETED")
    if verifier_actor_hash in forbidden:
        raise RuntimeError("verifier must be independent from approver and executor")
    events = conn.execute(
        """
        SELECT resource, key_hash, before_hash, after_hash
          FROM tenant_ownership_decision_event
         WHERE org_id=%s AND project_id=%s AND batch_id=%s
           AND event_type='APPLIED'
         ORDER BY resource, key_hash
        """,
        (owner_org_id, owner_project_id, batch_id),
    ).fetchall()
    rows = conn.execute(
        """
        SELECT user_key, relation, object_key, org_id, project_id
          FROM authz_tuple
        """
    ).fetchall()
    indexed = {
        stable_key_hash(
            "authz_tuple", str(row["user_key"]), str(row["relation"]),
            str(row["object_key"])
        ): row
        for row in rows
    }
    verified = 0
    for event in events:
        row = indexed.get(str(event["key_hash"]))
        if row is None:
            return {"batchId": batch_id, "gate": "BLOCKED", "verified": verified}
        current_hash = authz_content_hash(
            row, str(row["org_id"] or ""), str(row["project_id"] or "")
        )
        if current_hash != str(event["after_hash"]):
            return {"batchId": batch_id, "gate": "BLOCKED", "verified": verified}
        decision = {"resource": event["resource"], "key_hash": event["key_hash"]}
        _append_decision_event(
            conn,
            owner_org_id=owner_org_id,
            owner_project_id=owner_project_id,
            batch_id=batch_id,
            decision=decision,
            event_type="VERIFIED",
            before_hash=str(event["before_hash"]),
            after_hash=current_hash,
            actor_role="VERIFIER",
            actor_hash=verifier_actor_hash,
        )
        verified += 1
    return {"batchId": batch_id, "gate": "GREEN", "verified": verified}


def rollback_batch(
    conn: Any,
    *,
    owner_org_id: str,
    owner_project_id: str,
    batch_id: str,
    executor_actor_hash: str,
) -> dict[str, Any]:
    _lock_batch(conn, batch_id)
    events = conn.execute(
        """
        SELECT resource, key_hash, before_hash, after_hash
          FROM tenant_ownership_decision_event
         WHERE org_id=%s AND project_id=%s AND batch_id=%s
           AND event_type='APPLIED'
         ORDER BY resource, key_hash
        """,
        (owner_org_id, owner_project_id, batch_id),
    ).fetchall()
    rows = conn.execute(
        "SELECT user_key, relation, object_key, org_id, project_id FROM authz_tuple"
    ).fetchall()
    indexed = {
        stable_key_hash(
            "authz_tuple", str(row["user_key"]), str(row["relation"]),
            str(row["object_key"])
        ): row
        for row in rows
    }
    prepared: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    for event in events:
        row = indexed.get(str(event["key_hash"]))
        if row is None or authz_content_hash(
            row, str(row["org_id"] or ""), str(row["project_id"] or "")
        ) != str(event["after_hash"]):
            return {"batchId": batch_id, "gate": "BLOCKED", "rolledBack": 0}
        prepared.append((event, row))
    for event, row in prepared:
        updated = conn.execute(
            """
            UPDATE authz_tuple SET org_id=NULL, project_id=NULL
             WHERE user_key=%s AND relation=%s AND object_key=%s
               AND org_id=%s AND project_id=%s
            RETURNING user_key
            """,
            (
                row["user_key"], row["relation"], row["object_key"],
                row["org_id"], row["project_id"],
            ),
        ).fetchone()
        if not updated:
            raise RuntimeError("authz row changed during E3 rollback")
        decision = {"resource": event["resource"], "key_hash": event["key_hash"]}
        _append_decision_event(
            conn,
            owner_org_id=owner_org_id,
            owner_project_id=owner_project_id,
            batch_id=batch_id,
            decision=decision,
            event_type="ROLLED_BACK",
            before_hash=str(event["after_hash"]),
            after_hash=str(event["before_hash"]),
            actor_role="EXECUTOR",
            actor_hash=executor_actor_hash,
        )
    _append_batch_event(
        conn,
        owner_org_id=owner_org_id,
        owner_project_id=owner_project_id,
        batch_id=batch_id,
        status="ROLLED_BACK",
        evidence_hash=stable_key_hash(batch_id, "ROLLED_BACK", str(len(prepared))),
        actor_role="EXECUTOR",
        actor_hash=executor_actor_hash,
    )
    return {"batchId": batch_id, "gate": "GREEN", "rolledBack": len(prepared)}


def _lock_batch(conn: Any, batch_id: str) -> None:
    conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (batch_id,))


def _actor_hashes(
    conn: Any, org_id: str, project_id: str, batch_id: str, status: str
) -> set[str]:
    rows = conn.execute(
        """
        SELECT actor_hash FROM tenant_backfill_batch_event
         WHERE org_id=%s AND project_id=%s AND batch_id=%s AND status=%s
        """,
        (org_id, project_id, batch_id, status),
    ).fetchall()
    return {str(row["actor_hash"]) for row in rows}


def _batch_has_status(
    conn: Any, org_id: str, project_id: str, batch_id: str, status: str
) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM tenant_backfill_batch_event
         WHERE org_id=%s AND project_id=%s AND batch_id=%s AND status=%s
         LIMIT 1
        """,
        (org_id, project_id, batch_id, status),
    ).fetchone()
    return bool(row)


def _append_batch_event(
    conn: Any, *, owner_org_id: str, owner_project_id: str, batch_id: str,
    status: str, evidence_hash: str, actor_role: str, actor_hash: str,
) -> bool:
    if _batch_has_status(conn, owner_org_id, owner_project_id, batch_id, status):
        return False
    conn.execute(
        """
        INSERT INTO tenant_backfill_batch_event (
          org_id, project_id, batch_id, status, evidence_hash, actor_role,
          actor_hash
        ) VALUES (%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            owner_org_id, owner_project_id, batch_id, status, evidence_hash,
            actor_role, actor_hash,
        ),
    )
    return True


def _append_decision_event(
    conn: Any, *, owner_org_id: str, owner_project_id: str, batch_id: str,
    decision: Mapping[str, Any], event_type: str, before_hash: str,
    after_hash: str | None, actor_role: str, actor_hash: str,
) -> None:
    evidence_hash = stable_key_hash(
        batch_id, str(decision["resource"]), str(decision["key_hash"]),
        event_type, before_hash, after_hash or ""
    )
    conn.execute(
        """
        INSERT INTO tenant_ownership_decision_event (
          org_id, project_id, batch_id, resource, key_hash, event_type,
          before_hash, after_hash, evidence_hash, actor_role, actor_hash
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (
          org_id, project_id, batch_id, resource, key_hash, event_type
        ) DO NOTHING
        """,
        (
            owner_org_id, owner_project_id, batch_id, decision["resource"],
            decision["key_hash"], event_type, before_hash, after_hash,
            evidence_hash, actor_role, actor_hash,
        ),
    )


def _assign_decisions(
    conn: Any, org_id: str, project_id: str, batch_id: str
) -> Sequence[Mapping[str, Any]]:
    return conn.execute(
        """
        SELECT resource, key_hash, before_hash, target_org_id, target_project_id
          FROM tenant_ownership_decision
         WHERE org_id=%s AND project_id=%s AND batch_id=%s
           AND decision='ASSIGN'
         ORDER BY resource, key_hash
        """,
        (org_id, project_id, batch_id),
    ).fetchall()


def _unassigned_authz_rows(conn: Any) -> Sequence[Mapping[str, Any]]:
    return conn.execute(
        """
        SELECT user_key, relation, object_key
          FROM authz_tuple
         WHERE org_id IS NULL AND project_id IS NULL
         ORDER BY user_key, relation, object_key
        """
    ).fetchall()

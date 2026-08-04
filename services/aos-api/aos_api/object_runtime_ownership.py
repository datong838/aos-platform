"""TI-3 E3 Object runtime historical ownership quarantine (zero business DML)."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.tenant_backfill_executor import (
    _actor_hashes,
    _append_batch_event,
    _batch_has_status,
    _lock_batch,
)
from aos_api.tenant_dual_write import stable_key_hash

OWNER_SCOPE = ("dev-org", "dev-project")
NAMESPACE = uuid.UUID("6b5c76cb-d644-4eb4-8964-03fb8d2d3b2e")
TABLE_KEYS: dict[str, tuple[str, ...]] = {
    "draft_dataset": ("id",),
    "funnel_status": ("object_type",),
    "graph_edge": ("src_type", "src_id", "rel", "dst_type", "dst_id"),
    "meta_branch": ("id",),
    "obj_branch_overlay": ("branch_id", "object_type", "object_id"),
    "obj_instance": ("object_type", "object_id"),
    "object_lifecycle": ("object_type", "object_id"),
    "wiki_page": ("object_type", "object_id"),
    "wiki_page_version": ("id",),
}


def _rows(conn: Any, table: str, keys: tuple[str, ...]) -> list[Mapping[str, Any]]:
    columns = ", ".join(keys)
    order = ", ".join(keys)
    return list(
        conn.execute(
            f"SELECT {columns}, org_id, project_id, to_jsonb(t)::text AS row_json "
            f"FROM {table} t ORDER BY {order}"
        ).fetchall()
    )


def _key_hash(table: str, keys: tuple[str, ...], row: Mapping[str, Any]) -> str:
    return stable_key_hash("TI-3-E3", table, *(str(row[key]) for key in keys))


def _row_hash(table: str, row: Mapping[str, Any]) -> str:
    return stable_key_hash("TI-3-E3-ROW", table, str(row["row_json"]))


def build_plan(conn: Any, *, code_commit: str, batch_label: str) -> dict[str, Any]:
    workspaces = {
        (str(row["org_id"]), str(row["project_id"]))
        for row in conn.execute(
            "SELECT org_id, project_id FROM twa_workspace"
        ).fetchall()
    }
    decisions: list[dict[str, Any]] = []
    table_counts: dict[str, dict[str, int]] = {}
    for table, keys in TABLE_KEYS.items():
        rows = _rows(conn, table, keys)
        scoped = 0
        unknown = 0
        for row in rows:
            org_id = str(row["org_id"]) if row["org_id"] is not None else None
            project_id = (
                str(row["project_id"]) if row["project_id"] is not None else None
            )
            if org_id is None or project_id is None:
                decision = "QUARANTINE"
                grade = "X"
                reason = "TENANT_SCOPE_UNPROVEN"
                unknown += 1
            elif (org_id, project_id) not in workspaces:
                decision = "QUARANTINE"
                grade = "X"
                reason = "WORKSPACE_PARENT_NOT_FOUND"
                unknown += 1
            else:
                decision = "NO_ACTION"
                grade = "A"
                reason = "EXISTING_SCOPED_WORKSPACE"
                scoped += 1
            key_hash = _key_hash(table, keys, row)
            before_hash = _row_hash(table, row)
            decisions.append(
                {
                    "resource": table,
                    "keyHash": key_hash,
                    "decision": decision,
                    "evidenceGrade": grade,
                    "evidenceHash": stable_key_hash(
                        table, key_hash, decision, reason, before_hash
                    ),
                    "candidateCount": 1 if decision == "NO_ACTION" else 0,
                    "targetOrgId": org_id if decision == "NO_ACTION" else None,
                    "targetProjectId": project_id if decision == "NO_ACTION" else None,
                    "beforeHash": before_hash,
                    "afterHash": before_hash if decision == "NO_ACTION" else None,
                    "reasonCode": reason,
                }
            )
        table_counts[table] = {
            "total": len(rows),
            "scoped": scoped,
            "quarantine": unknown,
        }
    counts = _counts(decisions)
    snapshot = {"tableCounts": table_counts, "decisions": decisions}
    source_hash = canonical_sha256(snapshot).removeprefix("sha256:")
    batch_id = uuid.uuid5(
        NAMESPACE, f"TI-3-E3/{source_hash}/{code_commit}/{batch_label}"
    )
    return {
        "stage": "TI-3-E3",
        "gate": "GREEN" if counts["BLOCKED"] == 0 else "BLOCKED",
        "batchId": str(batch_id),
        "batchLabel": batch_label,
        "codeCommit": code_commit,
        "sourceSnapshotHash": source_hash,
        "decisionSummaryHash": canonical_sha256(decisions).removeprefix("sha256:"),
        "tableCounts": table_counts,
        "decisionCounts": counts,
        "decisions": decisions,
    }


def _counts(decisions: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    result = {name: 0 for name in ("ASSIGN", "QUARANTINE", "NO_ACTION", "BLOCKED")}
    for item in decisions:
        result[str(item["decision"])] += 1
    return result


def persist_plan(
    conn: Any,
    *,
    plan: Mapping[str, Any],
    environment_hash: str,
    planner_actor_hash: str,
) -> dict[str, Any]:
    if plan["gate"] != "GREEN" or plan["decisionCounts"]["ASSIGN"] != 0:
        raise RuntimeError("TI-3 E3 only accepts zero-assign GREEN plans")
    batch_id = str(plan["batchId"])
    _lock_batch(conn, batch_id)
    existing = conn.execute(
        "SELECT 1 FROM tenant_backfill_batch WHERE org_id=%s AND project_id=%s "
        "AND batch_id=%s",
        (*OWNER_SCOPE, batch_id),
    ).fetchone()
    if existing:
        return {"batchId": batch_id, "replayed": True}
    conn.execute(
        """
        INSERT INTO tenant_backfill_batch (
          org_id, project_id, batch_id, environment_hash,
          source_snapshot_hash, code_commit, mode, status
        ) VALUES (%s,%s,%s,%s,%s,%s,'NON_PROD','PLANNED')
        """,
        (
            *OWNER_SCOPE,
            batch_id,
            environment_hash,
            plan["sourceSnapshotHash"],
            plan["codeCommit"],
        ),
    )
    _append_batch_event(
        conn,
        owner_org_id=OWNER_SCOPE[0],
        owner_project_id=OWNER_SCOPE[1],
        batch_id=batch_id,
        status="PLANNED",
        evidence_hash=str(plan["decisionSummaryHash"]),
        actor_role="PLANNER",
        actor_hash=planner_actor_hash,
    )
    for item in plan["decisions"]:
        conn.execute(
            """
            INSERT INTO tenant_ownership_decision (
              org_id, project_id, batch_id, resource, key_hash, decision,
              evidence_grade, evidence_hash, candidate_count, target_org_id,
              target_project_id, before_hash, after_hash, reason_code
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                *OWNER_SCOPE,
                batch_id,
                item["resource"],
                item["keyHash"],
                item["decision"],
                item["evidenceGrade"],
                item["evidenceHash"],
                item["candidateCount"],
                item["targetOrgId"],
                item["targetProjectId"],
                item["beforeHash"],
                item["afterHash"],
                item["reasonCode"],
            ),
        )
        if item["decision"] == "QUARANTINE":
            conn.execute(
                """
                INSERT INTO tenant_quarantine_record (
                  org_id, project_id, batch_id, resource, key_hash,
                  reason_code, source_snapshot_hash
                ) VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    *OWNER_SCOPE,
                    batch_id,
                    item["resource"],
                    item["keyHash"],
                    item["reasonCode"],
                    plan["sourceSnapshotHash"],
                ),
            )
    return {"batchId": batch_id, "replayed": False}


def approve_plan(conn: Any, *, batch_id: str, approver_actor_hash: str) -> None:
    _lock_batch(conn, batch_id)
    _require_distinct_actor(conn, batch_id, approver_actor_hash)
    _append_batch_event(
        conn,
        owner_org_id=OWNER_SCOPE[0],
        owner_project_id=OWNER_SCOPE[1],
        batch_id=batch_id,
        status="APPROVED",
        evidence_hash=stable_key_hash(batch_id, "APPROVED"),
        actor_role="APPROVER",
        actor_hash=approver_actor_hash,
    )


def apply_plan(conn: Any, *, batch_id: str, executor_actor_hash: str) -> dict[str, Any]:
    _lock_batch(conn, batch_id)
    if not _batch_has_status(conn, *OWNER_SCOPE, batch_id, "APPROVED"):
        raise RuntimeError("TI-3 E3 batch is not approved")
    _require_distinct_actor(conn, batch_id, executor_actor_hash)
    batch = conn.execute(
        "SELECT source_snapshot_hash, code_commit FROM tenant_backfill_batch "
        "WHERE org_id=%s AND project_id=%s AND batch_id=%s",
        (*OWNER_SCOPE, batch_id),
    ).fetchone()
    current = build_plan(
        conn, code_commit=str(batch["code_commit"]), batch_label="verify"
    )
    if current["sourceSnapshotHash"] != str(batch["source_snapshot_hash"]):
        raise RuntimeError("TI-3 E3 source snapshot drifted before apply")
    _append_batch_event(
        conn,
        owner_org_id=OWNER_SCOPE[0],
        owner_project_id=OWNER_SCOPE[1],
        batch_id=batch_id,
        status="EXECUTING",
        evidence_hash=stable_key_hash(batch_id, "EXECUTING", "zero-business-dml"),
        actor_role="EXECUTOR",
        actor_hash=executor_actor_hash,
    )
    _append_batch_event(
        conn,
        owner_org_id=OWNER_SCOPE[0],
        owner_project_id=OWNER_SCOPE[1],
        batch_id=batch_id,
        status="COMPLETED",
        evidence_hash=stable_key_hash(batch_id, "COMPLETED", "0"),
        actor_role="EXECUTOR",
        actor_hash=executor_actor_hash,
    )
    return {"batchId": batch_id, "gate": "GREEN", "businessRowsUpdated": 0}


def verify_plan(
    conn: Any, *, batch_id: str, verifier_actor_hash: str
) -> dict[str, Any]:
    _lock_batch(conn, batch_id)
    _require_distinct_actor(conn, batch_id, verifier_actor_hash)
    batch = conn.execute(
        "SELECT source_snapshot_hash, code_commit FROM tenant_backfill_batch "
        "WHERE org_id=%s AND project_id=%s AND batch_id=%s",
        (*OWNER_SCOPE, batch_id),
    ).fetchone()
    current = build_plan(
        conn, code_commit=str(batch["code_commit"]), batch_label="verify"
    )
    gate = (
        "GREEN"
        if current["sourceSnapshotHash"] == str(batch["source_snapshot_hash"])
        else "BLOCKED"
    )
    quarantined = conn.execute(
        "SELECT COUNT(*) AS c FROM tenant_quarantine_record "
        "WHERE org_id=%s AND project_id=%s AND batch_id=%s",
        (*OWNER_SCOPE, batch_id),
    ).fetchone()["c"]
    return {
        "batchId": batch_id,
        "gate": gate,
        "verified": sum(v["total"] for v in current["tableCounts"].values()),
        "quarantined": int(quarantined),
        "businessRowsUpdated": 0,
    }


def rollback_plan(
    conn: Any, *, batch_id: str, executor_actor_hash: str
) -> dict[str, Any]:
    """Record reversal of the zero-DML execution; append-only evidence remains."""
    _lock_batch(conn, batch_id)
    batch = conn.execute(
        "SELECT source_snapshot_hash, code_commit FROM tenant_backfill_batch "
        "WHERE org_id=%s AND project_id=%s AND batch_id=%s",
        (*OWNER_SCOPE, batch_id),
    ).fetchone()
    current = build_plan(
        conn, code_commit=str(batch["code_commit"]), batch_label="rollback"
    )
    if current["sourceSnapshotHash"] != str(batch["source_snapshot_hash"]):
        return {"batchId": batch_id, "gate": "BLOCKED", "businessRowsUpdated": 0}
    _append_batch_event(
        conn,
        owner_org_id=OWNER_SCOPE[0],
        owner_project_id=OWNER_SCOPE[1],
        batch_id=batch_id,
        status="ROLLED_BACK",
        evidence_hash=stable_key_hash(batch_id, "ROLLED_BACK", "0"),
        actor_role="EXECUTOR",
        actor_hash=executor_actor_hash,
    )
    return {"batchId": batch_id, "gate": "GREEN", "businessRowsUpdated": 0}


def _require_distinct_actor(conn: Any, batch_id: str, actor_hash: str) -> None:
    prior: set[str] = set()
    for status in ("PLANNED", "APPROVED", "COMPLETED"):
        prior |= _actor_hashes(conn, *OWNER_SCOPE, batch_id, status)
    if actor_hash in prior:
        raise RuntimeError("TI-3 E3 duties require distinct actors")

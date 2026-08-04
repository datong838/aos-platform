"""TI-2 E3 deterministic and reversible Module identity backfill."""
from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.module_identity import MODULE_IDENTITY_NAMESPACE, stable_module_pk
from aos_api.tenant_backfill_executor import (
    _actor_hashes,
    _append_batch_event,
    _append_decision_event,
    _batch_has_status,
    _lock_batch,
)
from aos_api.tenant_dual_write import stable_key_hash

OWNER_SCOPE = ("dev-org", "dev-project")
CHILDREN: dict[str, str] = {
    "module_canvas_config": "module_id",
    "module_deployment": "id",
    "module_events": "id",
    "module_interface": "module_id",
    "module_query": "id",
    "module_variable": "id",
    "module_widget_instance": "id",
}


def _key_hash(table: str, row: Mapping[str, Any], key_column: str) -> str:
    return stable_key_hash(
        "TI-2-E3",
        table,
        str(row["org_id"]),
        str(row["project_id"]),
        str(row[key_column]),
    )


def _identity_hash(
    table: str,
    row: Mapping[str, Any],
    key_column: str,
    *,
    module_pk: str | None,
    module_id_copy: str | None = None,
) -> str:
    return stable_key_hash(
        "TI-2-E3-IDENTITY",
        table,
        str(row["org_id"]),
        str(row["project_id"]),
        str(row[key_column]),
        str(row["module_id"] if table != "meta_module" else row["id"]),
        module_pk or "",
        module_id_copy or "",
    )


def _rows(conn: Any) -> tuple[list[Mapping[str, Any]], dict[str, list[Mapping[str, Any]]]]:
    parents = list(
        conn.execute(
            "SELECT id, org_id, project_id, module_pk, module_id "
            "FROM meta_module ORDER BY org_id, project_id, id"
        ).fetchall()
    )
    children: dict[str, list[Mapping[str, Any]]] = {}
    for table, key_column in CHILDREN.items():
        children[table] = list(
            conn.execute(
                f"SELECT {key_column}, module_id, org_id, project_id, module_pk "
                f"FROM {table} ORDER BY org_id, project_id, {key_column}"
            ).fetchall()
        )
    return parents, children


def build_plan(conn: Any, *, code_commit: str, batch_label: str) -> dict[str, Any]:
    parents, children = _rows(conn)
    parent_index = {
        (str(row["org_id"]), str(row["project_id"]), str(row["id"])): row
        for row in parents
    }
    decisions: list[dict[str, Any]] = []
    expected_pks: set[str] = set()
    blocked = 0
    for row in parents:
        expected = str(
            stable_module_pk(str(row["org_id"]), str(row["project_id"]), str(row["id"]))
        )
        if expected in expected_pks:
            blocked += 1
        expected_pks.add(expected)
        current_pk = str(row["module_pk"]) if row["module_pk"] else None
        current_id = str(row["module_id"]) if row["module_id"] else None
        if current_pk is None and current_id is None:
            decision, grade, reason = "ASSIGN", "A", "EXACT_SCOPED_PARENT"
        elif current_pk == expected and current_id == str(row["id"]):
            decision, grade, reason = "NO_ACTION", "A", "IDENTITY_ALREADY_MATCHES"
        else:
            decision, grade, reason = "BLOCKED", "X", "IDENTITY_CONFLICT"
            blocked += 1
        before_hash = _identity_hash(
            "meta_module", row, "id", module_pk=current_pk, module_id_copy=current_id
        )
        after_hash = _identity_hash(
            "meta_module",
            row,
            "id",
            module_pk=expected,
            module_id_copy=str(row["id"]),
        )
        decisions.append(
            _decision(
                "meta_module", row, "id", decision, grade, reason,
                before_hash, after_hash, expected,
            )
        )

    for table, rows in children.items():
        key_column = CHILDREN[table]
        for row in rows:
            parent = parent_index.get(
                (str(row["org_id"]), str(row["project_id"]), str(row["module_id"]))
            )
            current_pk = str(row["module_pk"]) if row["module_pk"] else None
            before_hash = _identity_hash(
                table, row, key_column, module_pk=current_pk
            )
            if parent is None:
                decisions.append(
                    _decision(
                        table, row, key_column, "QUARANTINE", "X",
                        "SCOPED_PARENT_NOT_FOUND", before_hash, None, None,
                    )
                )
                continue
            expected = str(
                stable_module_pk(
                    str(parent["org_id"]), str(parent["project_id"]), str(parent["id"])
                )
            )
            after_hash = _identity_hash(
                table, row, key_column, module_pk=expected
            )
            if current_pk is None:
                decision, grade, reason = "ASSIGN", "A", "EXACT_SCOPED_PARENT"
            elif current_pk == expected:
                decision, grade, reason = "NO_ACTION", "A", "IDENTITY_ALREADY_MATCHES"
            else:
                decision, grade, reason = "BLOCKED", "X", "IDENTITY_CONFLICT"
                blocked += 1
            decisions.append(
                _decision(
                    table, row, key_column, decision, grade, reason,
                    before_hash, after_hash, expected,
                )
            )

    public_decisions = [
        {k: v for k, v in item.items() if k not in {"expectedModulePk"}}
        for item in decisions
    ]
    snapshot = {
        "parentRows": len(parents),
        "childRows": sum(len(rows) for rows in children.values()),
        "scopeCounts": _scope_counts(parents),
        "decisionCounts": _counts(decisions),
        "decisions": public_decisions,
    }
    source_hash = canonical_sha256(snapshot).removeprefix("sha256:")
    batch_id = uuid.uuid5(
        MODULE_IDENTITY_NAMESPACE,
        f"TI-2-E3/{source_hash}/{code_commit}/{batch_label}",
    )
    return {
        "stage": "TI-2-E3",
        "gate": "GREEN" if blocked == 0 else "BLOCKED",
        "batchId": str(batch_id),
        "batchLabel": batch_label,
        "codeCommit": code_commit,
        "sourceSnapshotHash": source_hash,
        "decisionSummaryHash": canonical_sha256(public_decisions).removeprefix("sha256:"),
        "parentRows": len(parents),
        "childRows": sum(len(rows) for rows in children.values()),
        "scopeCounts": _scope_counts(parents),
        "decisionCounts": _counts(decisions),
        "decisions": decisions,
    }


def _decision(
    table: str,
    row: Mapping[str, Any],
    key_column: str,
    decision: str,
    grade: str,
    reason: str,
    before_hash: str,
    after_hash: str | None,
    expected_pk: str | None,
) -> dict[str, Any]:
    evidence_hash = stable_key_hash(
        table, _key_hash(table, row, key_column), decision, reason,
        before_hash, after_hash or "",
    )
    return {
        "resource": table,
        "keyHash": _key_hash(table, row, key_column),
        "decision": decision,
        "evidenceGrade": grade,
        "evidenceHash": evidence_hash,
        "candidateCount": 1 if decision in {"ASSIGN", "NO_ACTION"} else 0,
        "targetOrgId": str(row["org_id"]) if decision == "ASSIGN" else None,
        "targetProjectId": str(row["project_id"]) if decision == "ASSIGN" else None,
        "beforeHash": before_hash,
        "afterHash": after_hash,
        "reasonCode": reason,
        "expectedModulePk": expected_pk,
    }


def _counts(decisions: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    result = {name: 0 for name in ("ASSIGN", "QUARANTINE", "NO_ACTION", "BLOCKED")}
    for item in decisions:
        result[str(item["decision"])] += 1
    return result


def _scope_counts(parents: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in parents:
        key = f"{row['org_id']}/{row['project_id']}"
        result[key] = result.get(key, 0) + 1
    return dict(sorted(result.items()))


def persist_plan(
    conn: Any,
    *,
    plan: Mapping[str, Any],
    environment_hash: str,
    planner_actor_hash: str,
) -> dict[str, Any]:
    if plan["gate"] != "GREEN":
        raise RuntimeError("cannot persist blocked TI-2 E3 plan")
    owner_org, owner_project = OWNER_SCOPE
    batch_id = str(plan["batchId"])
    _lock_batch(conn, batch_id)
    existing = conn.execute(
        "SELECT 1 FROM tenant_backfill_batch WHERE org_id=%s AND project_id=%s "
        "AND batch_id=%s",
        (owner_org, owner_project, batch_id),
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
            owner_org, owner_project, batch_id, environment_hash,
            plan["sourceSnapshotHash"], plan["codeCommit"],
        ),
    )
    _append_batch_event(
        conn,
        owner_org_id=owner_org,
        owner_project_id=owner_project,
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
              evidence_grade, evidence_hash, candidate_count,
              target_org_id, target_project_id, before_hash, after_hash, reason_code
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                owner_org, owner_project, batch_id, item["resource"], item["keyHash"],
                item["decision"], item["evidenceGrade"], item["evidenceHash"],
                item["candidateCount"], item["targetOrgId"], item["targetProjectId"],
                item["beforeHash"], item["afterHash"], item["reasonCode"],
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
                    owner_org, owner_project, batch_id, item["resource"],
                    item["keyHash"], item["reasonCode"], plan["sourceSnapshotHash"],
                ),
            )
    return {"batchId": batch_id, "replayed": False}


def approve_plan(conn: Any, *, batch_id: str, approver_actor_hash: str) -> None:
    owner_org, owner_project = OWNER_SCOPE
    _lock_batch(conn, batch_id)
    _require_distinct_actor(conn, batch_id, approver_actor_hash)
    _append_batch_event(
        conn, owner_org_id=owner_org, owner_project_id=owner_project,
        batch_id=batch_id, status="APPROVED",
        evidence_hash=stable_key_hash(batch_id, "APPROVED"),
        actor_role="APPROVER", actor_hash=approver_actor_hash,
    )


def apply_plan(conn: Any, *, batch_id: str, executor_actor_hash: str) -> dict[str, Any]:
    owner_org, owner_project = OWNER_SCOPE
    _lock_batch(conn, batch_id)
    if not _batch_has_status(conn, owner_org, owner_project, batch_id, "APPROVED"):
        raise RuntimeError("TI-2 E3 batch is not approved")
    _require_distinct_actor(conn, batch_id, executor_actor_hash)
    decisions = _assign_decisions(conn, batch_id)
    candidates = _candidate_index(conn)
    prepared: list[tuple[Mapping[str, Any], Mapping[str, Any], str]] = []
    for decision in decisions:
        row = candidates.get((str(decision["resource"]), str(decision["key_hash"])))
        if row is None:
            raise RuntimeError("TI-2 E3 candidate disappeared")
        before_hash = _current_hash(str(decision["resource"]), row)
        if before_hash != str(decision["before_hash"]):
            raise RuntimeError("TI-2 E3 candidate changed before apply")
        expected = _expected_pk(str(decision["resource"]), row)
        after_hash = _expected_hash(str(decision["resource"]), row, expected)
        if after_hash != str(decision["after_hash"]):
            raise RuntimeError("TI-2 E3 expected identity drift")
        prepared.append((decision, row, expected))
    _append_batch_event(
        conn, owner_org_id=owner_org, owner_project_id=owner_project,
        batch_id=batch_id, status="EXECUTING",
        evidence_hash=stable_key_hash(batch_id, "EXECUTING", str(len(prepared))),
        actor_role="EXECUTOR", actor_hash=executor_actor_hash,
    )
    for decision, row, expected in prepared:
        _apply_row(conn, str(decision["resource"]), row, expected)
        _append_decision_event(
            conn, owner_org_id=owner_org, owner_project_id=owner_project,
            batch_id=batch_id, decision=decision, event_type="APPLIED",
            before_hash=str(decision["before_hash"]),
            after_hash=str(decision["after_hash"]), actor_role="EXECUTOR",
            actor_hash=executor_actor_hash,
        )
    _append_batch_event(
        conn, owner_org_id=owner_org, owner_project_id=owner_project,
        batch_id=batch_id, status="COMPLETED",
        evidence_hash=stable_key_hash(batch_id, "COMPLETED", str(len(prepared))),
        actor_role="EXECUTOR", actor_hash=executor_actor_hash,
    )
    return {"batchId": batch_id, "gate": "GREEN", "applied": len(prepared)}


def verify_plan(conn: Any, *, batch_id: str, verifier_actor_hash: str) -> dict[str, Any]:
    owner_org, owner_project = OWNER_SCOPE
    _lock_batch(conn, batch_id)
    _require_distinct_actor(conn, batch_id, verifier_actor_hash)
    decisions = _assign_decisions(conn, batch_id)
    candidates = _candidate_index(conn)
    verified = 0
    for decision in decisions:
        row = candidates.get((str(decision["resource"]), str(decision["key_hash"])))
        if row is None or _current_hash(str(decision["resource"]), row) != str(
            decision["after_hash"]
        ):
            return {"batchId": batch_id, "gate": "BLOCKED", "verified": verified}
        _append_decision_event(
            conn, owner_org_id=owner_org, owner_project_id=owner_project,
            batch_id=batch_id, decision=decision, event_type="VERIFIED",
            before_hash=str(decision["before_hash"]),
            after_hash=str(decision["after_hash"]), actor_role="VERIFIER",
            actor_hash=verifier_actor_hash,
        )
        verified += 1
    return {"batchId": batch_id, "gate": "GREEN", "verified": verified}


def rollback_plan(conn: Any, *, batch_id: str, executor_actor_hash: str) -> dict[str, Any]:
    owner_org, owner_project = OWNER_SCOPE
    _lock_batch(conn, batch_id)
    events = conn.execute(
        """
        SELECT resource, key_hash, before_hash, after_hash
         FROM tenant_ownership_decision_event
         WHERE org_id=%s AND project_id=%s AND batch_id=%s AND event_type='APPLIED'
         ORDER BY CASE WHEN resource='meta_module' THEN 1 ELSE 0 END,
                  resource, key_hash
        """,
        (owner_org, owner_project, batch_id),
    ).fetchall()
    candidates = _candidate_index(conn)
    prepared: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    for event in events:
        row = candidates.get((str(event["resource"]), str(event["key_hash"])))
        if row is None or _current_hash(str(event["resource"]), row) != str(
            event["after_hash"]
        ):
            return {"batchId": batch_id, "gate": "BLOCKED", "rolledBack": 0}
        prepared.append((event, row))
    for event, row in prepared:
        _rollback_row(conn, str(event["resource"]), row)
        _append_decision_event(
            conn, owner_org_id=owner_org, owner_project_id=owner_project,
            batch_id=batch_id, decision=event, event_type="ROLLED_BACK",
            before_hash=str(event["after_hash"]), after_hash=str(event["before_hash"]),
            actor_role="EXECUTOR", actor_hash=executor_actor_hash,
        )
    _append_batch_event(
        conn, owner_org_id=owner_org, owner_project_id=owner_project,
        batch_id=batch_id, status="ROLLED_BACK",
        evidence_hash=stable_key_hash(batch_id, "ROLLED_BACK", str(len(prepared))),
        actor_role="EXECUTOR", actor_hash=executor_actor_hash,
    )
    return {"batchId": batch_id, "gate": "GREEN", "rolledBack": len(prepared)}


def _require_distinct_actor(conn: Any, batch_id: str, actor_hash: str) -> None:
    owner_org, owner_project = OWNER_SCOPE
    prior: set[str] = set()
    for status in ("PLANNED", "APPROVED", "COMPLETED"):
        prior |= _actor_hashes(conn, owner_org, owner_project, batch_id, status)
    if actor_hash in prior:
        raise RuntimeError("TI-2 E3 duties require distinct actors")


def _assign_decisions(conn: Any, batch_id: str) -> Sequence[Mapping[str, Any]]:
    return conn.execute(
        """
        SELECT resource, key_hash, before_hash, after_hash
          FROM tenant_ownership_decision
         WHERE org_id=%s AND project_id=%s AND batch_id=%s AND decision='ASSIGN'
         ORDER BY resource, key_hash
        """,
        (*OWNER_SCOPE, batch_id),
    ).fetchall()


def _candidate_index(conn: Any) -> dict[tuple[str, str], Mapping[str, Any]]:
    parents, children = _rows(conn)
    result: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in parents:
        result[("meta_module", _key_hash("meta_module", row, "id"))] = row
    for table, rows in children.items():
        for row in rows:
            result[(table, _key_hash(table, row, CHILDREN[table]))] = row
    return result


def _expected_pk(table: str, row: Mapping[str, Any]) -> str:
    if table == "meta_module":
        module_id = str(row["id"])
    else:
        module_id = str(row["module_id"])
    return str(stable_module_pk(str(row["org_id"]), str(row["project_id"]), module_id))


def _current_hash(table: str, row: Mapping[str, Any]) -> str:
    key_column = "id" if table == "meta_module" else CHILDREN[table]
    return _identity_hash(
        table,
        row,
        key_column,
        module_pk=str(row["module_pk"]) if row["module_pk"] else None,
        module_id_copy=(str(row["module_id"]) if row["module_id"] else None)
        if table == "meta_module"
        else None,
    )


def _expected_hash(table: str, row: Mapping[str, Any], expected: str) -> str:
    key_column = "id" if table == "meta_module" else CHILDREN[table]
    return _identity_hash(
        table, row, key_column, module_pk=expected,
        module_id_copy=str(row["id"]) if table == "meta_module" else None,
    )


def _apply_row(conn: Any, table: str, row: Mapping[str, Any], expected: str) -> None:
    if table == "meta_module":
        updated = conn.execute(
            "UPDATE meta_module SET module_pk=%s, module_id=id "
            "WHERE id=%s AND org_id=%s AND project_id=%s "
            "AND module_pk IS NULL AND module_id IS NULL RETURNING id",
            (expected, row["id"], row["org_id"], row["project_id"]),
        ).fetchone()
    else:
        key_column = CHILDREN[table]
        updated = conn.execute(
            f"UPDATE {table} SET module_pk=%s WHERE {key_column}=%s "
            "AND org_id=%s AND project_id=%s AND module_pk IS NULL "
            f"RETURNING {key_column}",
            (expected, row[key_column], row["org_id"], row["project_id"]),
        ).fetchone()
    if not updated:
        raise RuntimeError("TI-2 E3 compare-and-set failed")


def _rollback_row(conn: Any, table: str, row: Mapping[str, Any]) -> None:
    if table == "meta_module":
        updated = conn.execute(
            "UPDATE meta_module SET module_pk=NULL, module_id=NULL "
            "WHERE id=%s AND org_id=%s AND project_id=%s AND module_pk=%s "
            "AND module_id=id RETURNING id",
            (row["id"], row["org_id"], row["project_id"], row["module_pk"]),
        ).fetchone()
    else:
        key_column = CHILDREN[table]
        updated = conn.execute(
            f"UPDATE {table} SET module_pk=NULL WHERE {key_column}=%s "
            "AND org_id=%s AND project_id=%s AND module_pk=%s "
            f"RETURNING {key_column}",
            (row[key_column], row["org_id"], row["project_id"], row["module_pk"]),
        ).fetchone()
    if not updated:
        raise RuntimeError("TI-2 E3 rollback compare-and-set failed")

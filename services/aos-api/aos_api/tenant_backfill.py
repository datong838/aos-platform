"""Persistence primitives for TI-1 E3 dry-run and later reversible batches."""
from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any

from aos_api.asset_registry.canonical_json import canonical_sha256


def deterministic_batch_id(
    *, owner_org_id: str, owner_project_id: str, source_snapshot_hash: str,
    code_commit: str,
) -> uuid.UUID:
    identity = (
        f"{owner_org_id}:{owner_project_id}:{source_snapshot_hash}:{code_commit}"
    )
    return uuid.uuid5(uuid.NAMESPACE_URL, f"aos:tenant-e3:{identity}")


def persist_dry_run_batch(
    conn: Any,
    *,
    owner_org_id: str,
    owner_project_id: str,
    environment_hash: str,
    code_commit: str,
    dry_run: Mapping[str, Any],
) -> dict[str, Any]:
    if dry_run.get("gate") != "GREEN":
        raise RuntimeError("cannot persist a blocked E3 dry-run")
    source_snapshot_hash = str(dry_run["sourceSnapshotHash"])
    batch_id = deterministic_batch_id(
        owner_org_id=owner_org_id,
        owner_project_id=owner_project_id,
        source_snapshot_hash=source_snapshot_hash,
        code_commit=code_commit,
    )
    conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (str(batch_id),))
    existing = conn.execute(
        """
        SELECT source_snapshot_hash, code_commit
          FROM tenant_backfill_batch
         WHERE org_id=%s AND project_id=%s AND batch_id=%s
        """,
        (owner_org_id, owner_project_id, batch_id),
    ).fetchone()
    if existing:
        if (
            str(existing["source_snapshot_hash"]) != source_snapshot_hash
            or str(existing["code_commit"]) != code_commit
        ):
            raise RuntimeError("existing E3 batch identity does not match")
        return {
            "batchId": str(batch_id),
            "replayed": True,
            "decisionCount": int(dry_run["totalDiscovered"]),
        }

    conn.execute(
        """
        INSERT INTO tenant_backfill_batch (
          org_id, project_id, batch_id, environment_hash,
          source_snapshot_hash, code_commit, mode, status
        ) VALUES (%s,%s,%s,%s,%s,%s,'DRY_RUN','PLANNED')
        """,
        (
            owner_org_id,
            owner_project_id,
            batch_id,
            environment_hash,
            source_snapshot_hash,
            code_commit,
        ),
    )
    summary_hash = str(dry_run["decisionSummaryHash"])
    conn.execute(
        """
        INSERT INTO tenant_backfill_batch_event (
          org_id, project_id, batch_id, status, evidence_hash, actor_role
        ) VALUES (%s,%s,%s,'PLANNED',%s,'PLANNER')
        """,
        (owner_org_id, owner_project_id, batch_id, summary_hash),
    )
    for item in dry_run.get("decisions") or []:
        conn.execute(
            """
            INSERT INTO tenant_ownership_decision (
              org_id, project_id, batch_id, resource, key_hash, decision,
              evidence_grade, evidence_hash, candidate_count,
              target_org_id, target_project_id, before_hash, after_hash,
              reason_code
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,NULL,%s,NULL,%s)
            """,
            (
                owner_org_id,
                owner_project_id,
                batch_id,
                item["resource"],
                item["keyHash"],
                item["decision"],
                item["evidenceGrade"],
                item["evidenceHash"],
                item["candidateCount"],
                item["beforeHash"],
                item["reasonCode"],
            ),
        )
        if item["decision"] == "QUARANTINE":
            conn.execute(
                """
                INSERT INTO tenant_quarantine_record (
                  org_id, project_id, batch_id, resource, key_hash,
                  reason_code, candidate_scope_hashes, source_snapshot_hash
                ) VALUES (%s,%s,%s,%s,%s,%s,'[]'::jsonb,%s)
                """,
                (
                    owner_org_id,
                    owner_project_id,
                    batch_id,
                    item["resource"],
                    item["keyHash"],
                    item["reasonCode"],
                    source_snapshot_hash,
                ),
            )
    return {
        "batchId": str(batch_id),
        "replayed": False,
        "decisionCount": int(dry_run["totalDiscovered"]),
        "persistedEvidenceHash": canonical_sha256(dry_run),
    }

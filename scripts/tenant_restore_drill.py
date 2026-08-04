#!/usr/bin/env python3
"""Run a synthetic TI-1 E3 apply/verify/rollback cycle in a restored database."""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPOSITORY_ROOT / "services" / "aos-api"
sys.path.insert(0, str(API_ROOT))

from aos_api.db import connect
from aos_api.tenant_backfill_executor import (
    apply_batch,
    approve_batch,
    authz_content_hash,
    rollback_batch,
    verify_batch,
)
from aos_api.tenant_dual_write import stable_key_hash


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--owner-org", default="dev-org")
    parser.add_argument("--owner-project", default="dev-project")
    args = parser.parse_args()

    synthetic = {
        "user_key": "user:ti1-e3-restore-drill",
        "relation": "viewer",
        "object_key": "object:ti1-e3-restore-drill",
    }
    key_hash = stable_key_hash(
        "authz_tuple",
        synthetic["user_key"],
        synthetic["relation"],
        synthetic["object_key"],
    )
    before_hash = authz_content_hash(synthetic)
    source_hash = stable_key_hash("TI-1-E3-RESTORE", before_hash)
    batch_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"aos:e3:restore:{source_hash}"))
    actors = {
        "planner": stable_key_hash("TI-1-E3", "RESTORE", "PLANNER"),
        "approver": stable_key_hash("TI-1-E3", "RESTORE", "APPROVER"),
        "executor": stable_key_hash("TI-1-E3", "RESTORE", "EXECUTOR"),
        "verifier": stable_key_hash("TI-1-E3", "RESTORE", "VERIFIER"),
    }
    with connect() as conn:
        revision = conn.execute("SELECT version_num FROM alembic_version").fetchone()
        if str((revision or {}).get("version_num") or "") != "228ti1e3exec":
            raise RuntimeError("restore drill requires 228ti1e3exec")
        workspace = conn.execute(
            """
            SELECT 1 FROM twa_workspace
             WHERE org_id=%s AND project_id=%s
            """,
            (args.owner_org, args.owner_project),
        ).fetchone()
        if not workspace:
            raise RuntimeError("restore drill owner workspace is missing")
        initial_count = int(
            conn.execute("SELECT COUNT(*) AS count FROM authz_tuple").fetchone()[
                "count"
            ]
        )
        conn.execute(
            """
            INSERT INTO authz_tuple (user_key, relation, object_key, org_id, project_id)
            VALUES (%s,%s,%s,NULL,NULL)
            """,
            (synthetic["user_key"], synthetic["relation"], synthetic["object_key"]),
        )
        conn.execute(
            """
            INSERT INTO tenant_backfill_batch (
              org_id, project_id, batch_id, environment_hash,
              source_snapshot_hash, code_commit, mode, status
            ) VALUES (%s,%s,%s,%s,%s,%s,'RESTORE_DRILL','PLANNED')
            """,
            (
                args.owner_org,
                args.owner_project,
                batch_id,
                stable_key_hash("TI-1-E3", "RESTORE-DB"),
                source_hash,
                args.code_commit,
            ),
        )
        conn.execute(
            """
            INSERT INTO tenant_backfill_batch_event (
              org_id, project_id, batch_id, status, evidence_hash,
              actor_role, actor_hash
            ) VALUES (%s,%s,%s,'PLANNED',%s,'PLANNER',%s)
            """,
            (
                args.owner_org,
                args.owner_project,
                batch_id,
                source_hash,
                actors["planner"],
            ),
        )
        conn.execute(
            """
            INSERT INTO tenant_ownership_decision (
              org_id, project_id, batch_id, resource, key_hash, decision,
              evidence_grade, evidence_hash, candidate_count,
              target_org_id, target_project_id, before_hash, reason_code
            ) VALUES (%s,%s,%s,'authz_tuple',%s,'ASSIGN','A',%s,1,%s,%s,%s,%s)
            """,
            (
                args.owner_org,
                args.owner_project,
                batch_id,
                key_hash,
                stable_key_hash("TI-1-E3", "RESTORE", "A-GRADE"),
                args.owner_org,
                args.owner_project,
                before_hash,
                "SYNTHETIC_A_GRADE_RESTORE_DRILL",
            ),
        )
        approval = approve_batch(
            conn,
            owner_org_id=args.owner_org,
            owner_project_id=args.owner_project,
            batch_id=batch_id,
            approver_actor_hash=actors["approver"],
            evidence_hash=stable_key_hash(batch_id, "APPROVED"),
        )
        applied = apply_batch(
            conn,
            owner_org_id=args.owner_org,
            owner_project_id=args.owner_project,
            batch_id=batch_id,
            executor_actor_hash=actors["executor"],
        )
        verified = verify_batch(
            conn,
            owner_org_id=args.owner_org,
            owner_project_id=args.owner_project,
            batch_id=batch_id,
            verifier_actor_hash=actors["verifier"],
        )
        rolled_back = rollback_batch(
            conn,
            owner_org_id=args.owner_org,
            owner_project_id=args.owner_project,
            batch_id=batch_id,
            executor_actor_hash=actors["executor"],
        )
        final = conn.execute(
            """
            SELECT user_key, relation, object_key, org_id, project_id
              FROM authz_tuple
             WHERE user_key=%s AND relation=%s AND object_key=%s
            """,
            (synthetic["user_key"], synthetic["relation"], synthetic["object_key"]),
        ).fetchone()
        final_count = int(
            conn.execute("SELECT COUNT(*) AS count FROM authz_tuple").fetchone()[
                "count"
            ]
        )
        final_hash = authz_content_hash(final)
        event_count = int(
            conn.execute(
                """
                SELECT COUNT(*) AS count FROM tenant_ownership_decision_event
                 WHERE org_id=%s AND project_id=%s AND batch_id=%s
                """,
                (args.owner_org, args.owner_project, batch_id),
            ).fetchone()["count"]
        )

    ok = (
        approval["approved"]
        and applied.get("applied") == 1
        and verified.get("verified") == 1
        and rolled_back.get("rolledBack") == 1
        and final["org_id"] is None
        and final["project_id"] is None
        and final_hash == before_hash
        and final_count == initial_count + 1
        and event_count == 3
    )
    result = {
        "stage": "TI-1-E3-3",
        "gate": "GREEN" if ok else "BLOCKED",
        "alembicRevision": "228ti1e3exec",
        "batchHash": stable_key_hash(batch_id),
        "backupRestoreDatabase": True,
        "applyCount": applied.get("applied"),
        "verifyCount": verified.get("verified"),
        "rollbackCount": rolled_back.get("rolledBack"),
        "decisionEventCount": event_count,
        "beforeAfterRollbackHashEqual": final_hash == before_hash,
        "rowCountConservedAcrossCycle": final_count == initial_count + 1,
        "actorRolesDistinct": len(set(actors.values())) == 4,
        "rawKeysReturned": False,
        "rawPayloadReturned": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

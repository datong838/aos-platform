#!/usr/bin/env python3
"""Generate the O1-UX2 exploration-asset persistence evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


KINDS = ("exploration", "object_set", "annotation")
HEADS = tuple(f"ontology_{kind}_asset_head" for kind in KINDS)
TABLES = tuple(
    [f"ontology_{kind}_asset_{suffix}" for kind in KINDS for suffix in ("head", "revision")]
    + ["ontology_object_set_item", "ontology_exploration_asset_receipt"]
)


def _git_sha(repo: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    target = TenantScope("org-org", "dev-project")
    canary = TenantScope("dev-org", "dev-project")

    with connect(target) as conn:
        migration = conn.execute("SELECT version_num FROM alembic_version").fetchone()["version_num"]
        rls_rows = conn.execute(
            "SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class "
            "WHERE relkind='r' AND relname=ANY(%s) ORDER BY relname",
            (list(TABLES),),
        ).fetchall()
        active_target = {
            table: int(conn.execute(f"SELECT count(*) AS n FROM {table} WHERE archived_at IS NULL").fetchone()["n"])
            for table in HEADS
        }
        archived_target = {
            table: int(conn.execute(f"SELECT count(*) AS n FROM {table} WHERE archived_at IS NOT NULL").fetchone()["n"])
            for table in HEADS
        }
        receipt_count = int(
            conn.execute("SELECT count(*) AS n FROM ontology_exploration_asset_receipt").fetchone()["n"]
        )
        archive_receipts = int(
            conn.execute(
                "SELECT count(*) AS n FROM ontology_exploration_asset_receipt WHERE operation='archive'"
            ).fetchone()["n"]
        )

    with connect(canary) as conn:
        cross_tenant_visible = {
            table: int(
                conn.execute(
                    f"SELECT count(*) AS n FROM {table} WHERE org_id=%s AND workspace_id=%s",
                    target.key,
                ).fetchone()["n"]
            )
            for table in TABLES
        }
        canary_active = {
            table: int(conn.execute(f"SELECT count(*) AS n FROM {table} WHERE archived_at IS NULL").fetchone()["n"])
            for table in HEADS
        }

    all_rls = len(rls_rows) == len(TABLES) and all(
        row["relrowsecurity"] and row["relforcerowsecurity"] for row in rls_rows
    )
    target_clean = all(value == 0 for value in active_target.values())
    canary_zero = all(value == 0 for value in cross_tenant_visible.values()) and all(
        value == 0 for value in canary_active.values()
    )
    audit_closed = sum(archived_target.values()) >= 4 and receipt_count >= 8 and archive_receipts >= 4
    checks = {
        "migration": migration == "o1ux2_001",
        "rlsAndForceRls": all_rls,
        "targetHasNoActiveAcceptanceAssets": target_clean,
        "archivedAcceptanceAuditRetained": audit_closed,
        "crossTenantCanary": canary_zero,
    }
    status = "GREEN" if all(checks.values()) else "RED"
    now = datetime.now(UTC)
    repo = Path(__file__).resolve().parents[3]
    payload = {
        "gate": "O1-UX2_PERSISTENCE_GATE",
        "status": status,
        "generatedAt": now.isoformat(),
        "gitSha": _git_sha(repo),
        "migrationHead": migration,
        "targetScope": {"orgId": target.org_id, "workspaceId": target.project_id},
        "canaryScope": {"orgId": canary.org_id, "workspaceId": canary.project_id},
        "tableCount": len(TABLES),
        "rlsForceCount": sum(
            1 for row in rls_rows if row["relrowsecurity"] and row["relforcerowsecurity"]
        ),
        "activeTargetAssets": active_target,
        "archivedTargetAssets": archived_target,
        "receiptCount": receipt_count,
        "archiveReceiptCount": archive_receipts,
        "crossTenantVisibleRows": sum(cross_tenant_visible.values()),
        "canaryActiveAssets": canary_active,
        "checks": checks,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload["evidenceSha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / f"O1-UX2_{now.strftime('%Y%m%dT%H%M%SZ')}.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    print(json.dumps({"status": status, "checks": checks}, ensure_ascii=False))
    return 0 if status == "GREEN" else 1


if __name__ == "__main__":
    raise SystemExit(main())

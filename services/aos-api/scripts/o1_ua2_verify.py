#!/usr/bin/env python3
"""Generate the O1-UA2 database authority gate evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


KINDS = (
    "knowledge", "action_type", "action_instance", "task", "plan", "checkpoint",
    "artifact", "eval", "evidence", "retention_policy",
)
RECEIPTS = (
    "ontology_authority_receipt",
    "ontology_authority_archive_receipt",
    "ontology_evidence_cleanup_receipt",
)
TABLES = tuple(
    [f"ontology_{kind}_{suffix}" for kind in KINDS for suffix in ("head", "revision")]
    + list(RECEIPTS)
)


def _git_sha(repo: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    target = TenantScope(org_id="org-org", project_id="dev-project")
    canary = TenantScope(org_id="dev-org", project_id="dev-project")
    with connect(target) as conn:
        migration = conn.execute("SELECT version_num FROM alembic_version").fetchone()["version_num"]
        rls_rows = conn.execute(
            "SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class WHERE relname=ANY(%s) ORDER BY relname",
            (list(TABLES),),
        ).fetchall()
        target_counts = {
            table: int(conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"])
            for table in TABLES
        }
    with connect(canary) as conn:
        cross_tenant_visible = {
            table: int(conn.execute(
                f"SELECT count(*) AS n FROM {table} WHERE org_id=%s AND workspace_id=%s",
                target.key,
            ).fetchone()["n"])
            for table in TABLES
        }
        installed = conn.execute(
            "SELECT count(*) AS n FROM bundle_installation WHERE org_id=%s AND project_id=%s",
            canary.key,
        ).fetchone()["n"]
    all_rls = len(rls_rows) == len(TABLES) and all(
        row["relrowsecurity"] and row["relforcerowsecurity"] for row in rls_rows
    )
    clean_target = all(count == 0 for count in target_counts.values())
    canary_zero = all(count == 0 for count in cross_tenant_visible.values())
    status = "GREEN" if migration == "o1ua2_002" and all_rls and clean_target and canary_zero and installed == 0 else "RED"
    now = datetime.now(UTC)
    repo = Path(__file__).resolve().parents[3]
    payload = {
        "gate": "O1-UA2_CONTRACT_GATE",
        "status": status,
        "generatedAt": now.isoformat(),
        "gitSha": _git_sha(repo),
        "migrationHead": migration,
        "targetScope": {"orgId": target.org_id, "workspaceId": target.project_id},
        "canaryScope": {"orgId": canary.org_id, "workspaceId": canary.project_id},
        "tableCount": len(TABLES),
        "rlsForceCount": sum(1 for row in rls_rows if row["relrowsecurity"] and row["relforcerowsecurity"]),
        "targetNewAuthorityRows": sum(target_counts.values()),
        "crossTenantVisibleRows": sum(cross_tenant_visible.values()),
        "canaryActiveInstallations": int(installed),
        "checks": {
            "migration": migration == "o1ua2_002",
            "rlsAndForceRls": all_rls,
            "targetRemainedReadOnlyAndClean": clean_target,
            "crossTenantCanary": canary_zero,
            "uninstalledCanary": installed == 0,
        },
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload["evidenceSha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / f"O1-UA2_{now.strftime('%Y%m%dT%H%M%SZ')}.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    print(json.dumps({"status": status, "checks": payload["checks"]}, ensure_ascii=False))
    return 0 if status == "GREEN" else 1


if __name__ == "__main__":
    raise SystemExit(main())

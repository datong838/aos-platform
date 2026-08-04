#!/usr/bin/env python3
"""Run TI-1 E3-0 read-only source snapshot and E1 reconciliation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPOSITORY_ROOT / "services" / "aos-api"
sys.path.insert(0, str(API_ROOT))

from aos_api.db import connect, get_dsn
from aos_api.tenant_dual_write import stable_key_hash
from aos_api.tenant_e3_rebaseline import (
    build_e1_reconciliation,
    read_e3_source_snapshot,
)
from aos_api.tenant_precheck import read_postgres_precheck


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--test-org", default="dev-org")
    parser.add_argument("--test-project", default="dev-project")
    parser.add_argument("--target-org", default="org-org")
    parser.add_argument("--target-project", default="dev-project")
    args = parser.parse_args()

    environment_fingerprint = stable_key_hash(get_dsn())
    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        postgres = read_postgres_precheck(
            conn,
            test_org_id=args.test_org,
            test_project_id=args.test_project,
            target_org_id=args.target_org,
            target_project_id=args.target_project,
        )
        source_snapshot = read_e3_source_snapshot(
            conn,
            postgres_precheck=postgres,
            environment_fingerprint=environment_fingerprint,
            target_org_id=args.target_org,
            target_project_id=args.target_project,
        )

    reconciliation = build_e1_reconciliation(source_snapshot)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(args.output_dir / "e3-source-snapshot.json", source_snapshot)
    _write_json(
        args.output_dir / "e3-baseline-reconciliation.json", reconciliation
    )
    summary = {
        "stage": "TI-1-E3-0",
        "gate": reconciliation["gate"],
        "blockers": reconciliation["blockers"],
        "alembicRevision": source_snapshot["alembicRevision"],
        "outputDir": str(args.output_dir.resolve()),
        "historyMutated": False,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if reconciliation["gate"] == "GREEN" else 2


if __name__ == "__main__":
    raise SystemExit(main())

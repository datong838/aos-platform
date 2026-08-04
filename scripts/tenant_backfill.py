#!/usr/bin/env python3
"""Generate and optionally persist a fail-closed TI-1 E3 dry-run batch."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPOSITORY_ROOT / "services" / "aos-api"
sys.path.insert(0, str(API_ROOT))

from aos_api.db import connect
from aos_api.tenant_backfill import persist_dry_run_batch
from aos_api.tenant_ownership_classifier import classify_source_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--owner-org", default="dev-org")
    parser.add_argument("--owner-project", default="dev-project")
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()

    source = json.loads(args.source_snapshot.read_text(encoding="utf-8"))
    dry_run = classify_source_snapshot(source)
    if args.persist:
        with connect() as conn:
            persisted = persist_dry_run_batch(
                conn,
                owner_org_id=args.owner_org,
                owner_project_id=args.owner_project,
                environment_hash=str(source["environmentFingerprint"]),
                code_commit=args.code_commit,
                dry_run=dry_run,
            )
        dry_run["persistence"] = persisted
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(dry_run, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "stage": dry_run["stage"],
        "gate": dry_run["gate"],
        "totalDiscovered": dry_run["totalDiscovered"],
        "counts": dry_run["counts"],
        "persistence": dry_run.get("persistence"),
        "output": str(args.output.resolve()),
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if dry_run["gate"] == "GREEN" else 2


if __name__ == "__main__":
    raise SystemExit(main())


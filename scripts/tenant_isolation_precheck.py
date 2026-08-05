#!/usr/bin/env python3
"""Run the TI-0D read-only ownership precheck and emit four redacted ledgers."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPOSITORY_ROOT / "services" / "aos-api"
sys.path.insert(0, str(API_ROOT))

from aos_api.db import connect
from aos_api.object_store import get_config, list_keys_with_prefix
from aos_api.tenant_precheck import (
    NOT_CONFIGURED,
    PROBE_ERROR,
    PROBED,
    build_migration_ledger,
    build_non_postgres_inventory,
    build_qiyue_baseline,
    postgres_scheduler_report,
    read_known_tenant_scopes,
    read_postgres_precheck,
    read_vector_report,
    scan_process_memory_sources,
    summarize_object_keys,
)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _object_store_report(
    *,
    test_org_id: str,
    test_project_id: str,
    target_org_id: str,
    target_project_id: str,
    known_tenant_scopes: set[tuple[str, str]],
) -> dict[str, Any]:
    config = get_config()
    if not config.enabled:
        return {
            "status": NOT_CONFIGURED,
            "backend": "s3-compatible",
            "itemCount": 0,
        }
    try:
        summary = summarize_object_keys(
            list_keys_with_prefix(prefix="", cfg=config),
            test_org_id=test_org_id,
            test_project_id=test_project_id,
            target_org_id=target_org_id,
            target_project_id=target_project_id,
            known_tenant_scopes=known_tenant_scopes,
        )
        return {
            "status": PROBED,
            "backend": "s3-compatible",
            "bucket": config.bucket,
            "contentInspected": False,
            **summary,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": PROBE_ERROR,
            "backend": "s3-compatible",
            "bucket": config.bucket,
            "errorClass": type(exc).__name__,
            "contentInspected": False,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--test-org", default="dev-org")
    parser.add_argument("--test-project", default="dev-project")
    parser.add_argument("--target-org", default="org-org")
    parser.add_argument("--target-project", default="dev-project")
    parser.add_argument(
        "--strict-proven-empty",
        action="store_true",
        help="return non-zero unless the target tenant is proven empty",
    )
    args = parser.parse_args()

    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        postgres = read_postgres_precheck(
            conn,
            test_org_id=args.test_org,
            test_project_id=args.test_project,
            target_org_id=args.target_org,
            target_project_id=args.target_project,
        )
        known_scopes = read_known_tenant_scopes(conn)
        vector = read_vector_report(
            conn,
            known_tenant_scopes=known_scopes,
            test_org_id=args.test_org,
            test_project_id=args.test_project,
            target_org_id=args.target_org,
            target_project_id=args.target_project,
        )

    object_store = _object_store_report(
        test_org_id=args.test_org,
        test_project_id=args.test_project,
        target_org_id=args.target_org,
        target_project_id=args.target_project,
        known_tenant_scopes=known_scopes,
    )
    process_memory = scan_process_memory_sources(API_ROOT / "aos_api")
    non_postgres = build_non_postgres_inventory(
        object_store_report=object_store,
        vector_report=vector,
        process_memory_report=process_memory,
        scheduler_report=postgres_scheduler_report(postgres),
    )
    ledger = build_migration_ledger(postgres)
    baseline = build_qiyue_baseline(postgres, non_postgres)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "ti0d-precheck.json": postgres,
        "ti0d-migration-ledger.json": ledger,
        "ti0d-qiyue-baseline.json": baseline,
        "ti0d-non-postgres-inventory.json": non_postgres,
    }
    for filename, value in outputs.items():
        _write_json(args.output_dir / filename, value)

    scan_ok = bool(postgres["scanOk"]) and object_store.get("status") != PROBE_ERROR
    summary = {
        "stage": "TI-0D",
        "scanOk": scan_ok,
        "isQiyueProvenEmpty": baseline["isProvenEmpty"],
        "qiyueBlockers": baseline["blockers"],
        "postgresTableCount": postgres["tableCount"],
        "postgresProbedTableCount": postgres["probedTableCount"],
        "migrationBlockerCounts": ledger["blockerCounts"],
        "nonPostgresStatusCounts": non_postgres["statusCounts"],
        "outputDir": str(args.output_dir.resolve()),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if not scan_ok:
        return 1
    if args.strict_proven_empty and not baseline["isProvenEmpty"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

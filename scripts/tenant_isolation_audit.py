#!/usr/bin/env python3
"""Emit the TI-0B tenant-resource registry and PostgreSQL coverage evidence."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPOSITORY_ROOT / "services" / "aos-api"
sys.path.insert(0, str(API_ROOT))

from aos_api.db import connect
from aos_api.tenant_resource_registry import (
    build_postgres_coverage_report,
    load_tenant_resource_registry,
    read_postgres_snapshot,
    validate_registry,
)


def _registry_summary(registry: dict[str, Any]) -> dict[str, Any]:
    resources = registry.get("resources") or []
    return {
        "schemaVersion": registry.get("schemaVersion"),
        "registryVersion": registry.get("registryVersion"),
        "ok": not validate_registry(registry),
        "validationIssues": validate_registry(registry),
        "resourceCount": len(resources),
        "kindCounts": dict(
            sorted(Counter(str(item.get("kind")) for item in resources).items())
        ),
        "classificationCounts": dict(
            sorted(
                Counter(
                    str(item.get("classification")) for item in resources
                ).items()
            )
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry-only",
        action="store_true",
        help="validate and summarize the registry without connecting to PostgreSQL",
    )
    parser.add_argument("--output", type=Path, help="write JSON evidence to this path")
    parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    args = parser.parse_args()

    registry = load_tenant_resource_registry()
    if args.registry_only:
        report = {"stage": "TI-0B", "registry": _registry_summary(registry)}
        ok = bool(report["registry"]["ok"])
    else:
        with connect() as conn:
            snapshots, policy_count = read_postgres_snapshot(conn)
        coverage = build_postgres_coverage_report(
            snapshots, policy_count=policy_count, registry=registry
        )
        report = {
            "stage": "TI-0B",
            "readiness": "TI-0B_GREEN_TI-1_REQUIRED"
            if coverage["ok"]
            else "TI-0B_DRIFT_DETECTED",
            "registry": _registry_summary(registry),
            "postgresCoverage": coverage,
        }
        ok = bool(coverage["ok"])

    encoded = json.dumps(
        report,
        ensure_ascii=False,
        indent=None if args.compact else 2,
        sort_keys=True,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

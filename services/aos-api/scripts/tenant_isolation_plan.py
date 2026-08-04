"""Compile TI-0E JSON artifacts from the registry and TI-0D evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from aos_api.tenant_migration_plan import build_ti0e_artifacts, content_sha256


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--migration-ledger", type=Path, required=True)
    parser.add_argument("--non-postgres-inventory", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    inputs = {
        "ti0dMigrationLedger": args.migration_ledger,
        "ti0dNonPostgresInventory": args.non_postgres_inventory,
    }
    artifacts = build_ti0e_artifacts(
        migration_ledger=_json(args.migration_ledger),
        non_postgres_inventory=_json(args.non_postgres_inventory),
        source_hashes={
            name: content_sha256(path.read_bytes()) for name, path in inputs.items()
        },
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for filename, payload in artifacts.items():
        (args.output_dir / filename).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

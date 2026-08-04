"""Run a TI-1 schema lint in a read-only transaction."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from aos_api.db import connect
from aos_api.tenant_schema_lint import (
    build_ti1_e1_schema_report,
    build_ti1_e2_schema_report,
    build_ti1_e3_schema_report,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--stage", choices=("e1", "e2", "e3"), default="e2")
    args = parser.parse_args()
    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        builders = {
            "e1": build_ti1_e1_schema_report,
            "e2": build_ti1_e2_schema_report,
            "e3": build_ti1_e3_schema_report,
        }
        report = builders[args.stage](conn)
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

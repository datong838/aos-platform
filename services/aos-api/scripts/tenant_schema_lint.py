"""Run the TI-1 E1 schema lint in a read-only transaction."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from aos_api.db import connect
from aos_api.tenant_schema_lint import build_ti1_e2_schema_report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        report = build_ti1_e2_schema_report(conn)
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

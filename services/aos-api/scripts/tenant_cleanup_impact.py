"""Print a TI-6-4 read-only cleanup impact plan for one exact tenant scope."""

from __future__ import annotations

import argparse
import json
import os

os.environ.setdefault("AOS_LOG_LEVEL", "warning")

from aos_api.db import connect
from aos_api.tenant_cleanup import build_cleanup_impact_plan
from aos_api.tenant_scope import TenantScope


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--org-id", required=True)
    parser.add_argument("--project-id", required=True)
    args = parser.parse_args()
    scope = TenantScope(args.org_id, args.project_id)
    with connect(scope) as conn:
        plan = build_cleanup_impact_plan(conn, scope)
    print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

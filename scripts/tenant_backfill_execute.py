#!/usr/bin/env python3
"""Approve, apply, verify, or roll back a TI-1 E3 batch."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPOSITORY_ROOT / "services" / "aos-api"
sys.path.insert(0, str(API_ROOT))

from aos_api.db import connect
from aos_api.tenant_backfill_executor import (
    apply_batch,
    approve_batch,
    rollback_batch,
    verify_batch,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("approve", "apply", "verify", "rollback"))
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--actor-hash", required=True)
    parser.add_argument("--evidence-hash")
    parser.add_argument("--owner-org", default="dev-org")
    parser.add_argument("--owner-project", default="dev-project")
    args = parser.parse_args()
    common = {
        "owner_org_id": args.owner_org,
        "owner_project_id": args.owner_project,
        "batch_id": args.batch_id,
    }
    with connect() as conn:
        if args.operation == "approve":
            if not args.evidence_hash:
                parser.error("approve requires --evidence-hash")
            result = approve_batch(
                conn,
                **common,
                approver_actor_hash=args.actor_hash,
                evidence_hash=args.evidence_hash,
            )
        elif args.operation == "apply":
            result = apply_batch(
                conn, **common, executor_actor_hash=args.actor_hash
            )
        elif args.operation == "verify":
            result = verify_batch(
                conn, **common, verifier_actor_hash=args.actor_hash
            )
        else:
            result = rollback_batch(
                conn, **common, executor_actor_hash=args.actor_hash
            )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("gate", "GREEN") == "GREEN" else 2


if __name__ == "__main__":
    raise SystemExit(main())


#!/usr/bin/env python3
"""Operate the TI-3 E3 Object runtime ownership quarantine state machine."""

from __future__ import annotations

import argparse
import json

from aos_api.db import connect
from aos_api.object_runtime_ownership import (
    apply_plan,
    approve_plan,
    build_plan,
    persist_plan,
    rollback_plan,
    verify_plan,
)
from aos_api.tenant_dual_write import stable_key_hash


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=("plan", "persist", "approve", "apply", "verify", "rollback")
    )
    parser.add_argument("--batch-id")
    parser.add_argument("--batch-label", default="manual")
    parser.add_argument("--code-commit", default="5e58768")
    parser.add_argument("--actor", default="local-operator")
    parser.add_argument("--environment", default="shared-nonprod")
    return parser


def main() -> int:
    args = _parser().parse_args()
    actor_hash = stable_key_hash("TI-3-E3-ACTOR", args.actor)
    with connect() as conn:
        if args.action in {"plan", "persist"}:
            plan = build_plan(
                conn, code_commit=args.code_commit, batch_label=args.batch_label
            )
            result: dict = {
                key: value for key, value in plan.items() if key != "decisions"
            }
            if args.action == "persist":
                result["persistence"] = persist_plan(
                    conn,
                    plan=plan,
                    environment_hash=stable_key_hash("TI-3-E3-ENV", args.environment),
                    planner_actor_hash=actor_hash,
                )
                conn.commit()
        else:
            if not args.batch_id:
                raise SystemExit("--batch-id is required for this action")
            if args.action == "approve":
                approve_plan(
                    conn, batch_id=args.batch_id, approver_actor_hash=actor_hash
                )
                result = {"batchId": args.batch_id, "approved": True}
            elif args.action == "apply":
                result = apply_plan(
                    conn, batch_id=args.batch_id, executor_actor_hash=actor_hash
                )
            elif args.action == "verify":
                result = verify_plan(
                    conn, batch_id=args.batch_id, verifier_actor_hash=actor_hash
                )
            else:
                result = rollback_plan(
                    conn, batch_id=args.batch_id, executor_actor_hash=actor_hash
                )
            conn.commit()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

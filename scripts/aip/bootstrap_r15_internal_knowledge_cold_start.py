#!/usr/bin/env python3
"""Plan or explicitly apply the governed R15 internal knowledge cold start."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICE_ROOT = REPO_ROOT / "services" / "aos-api"
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from aos_api.aip_memory_cold_start import (  # noqa: E402
    apply_internal_knowledge_seed,
    plan_internal_knowledge_seed,
)
from aos_api.tenant_scope import TenantScope  # noqa: E402

DEFAULT_SOURCE = REPO_ROOT / (
    "bundles/solutions/ecommerce-growth/content/knowledge/internal/"
    "qyh-customer-service-escalation-v1.md"
)
DEFAULT_LEASES = REPO_ROOT.parent / (
    "docs/palantier/AOS项目开发上下文/memory/leases.json"
)
REQUIRED_DB_SCOPE = "database-writes:org-org/dev-project"
REQUIRED_CODE_SCOPE = (
    "aos-platform-w1-aip:services/aos-api/aos_api/aip_memory_cold_start.py"
)


def _aware_datetime(raw: str) -> datetime:
    value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if value.utcoffset() is None:
        raise argparse.ArgumentTypeError("timestamp must include timezone")
    return value


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--org", default="org-org")
    result.add_argument("--project", default="dev-project")
    result.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    result.add_argument("--observed-at", type=_aware_datetime, required=True)
    result.add_argument("--freshness-expires-at", type=_aware_datetime, required=True)
    result.add_argument("--now", type=_aware_datetime, required=True)
    result.add_argument("--expected-hash")
    result.add_argument("--apply", action="store_true")
    result.add_argument("--actor")
    result.add_argument("--reviewer")
    result.add_argument("--lease-id")
    result.add_argument("--leases-file", type=Path, default=DEFAULT_LEASES)
    return result


def _require_apply_lease(args: argparse.Namespace) -> None:
    if not args.lease_id or not args.actor or not args.reviewer:
        raise ValueError("--apply requires --lease-id, --actor and --reviewer")
    if args.actor.strip() == args.reviewer.strip():
        raise ValueError("--actor and --reviewer must be different")
    document = json.loads(args.leases_file.read_text(encoding="utf-8"))
    lease = next(
        (
            item
            for item in document.get("leases", [])
            if item.get("task_id") == args.lease_id and item.get("status") == "ACTIVE"
        ),
        None,
    )
    if lease is None:
        raise ValueError("R15 apply requires one active matching Lease")
    expires_at = _aware_datetime(str(lease.get("lease_expires_at", "")))
    if expires_at <= args.now:
        raise ValueError("R15 apply Lease is expired")
    scope = set(lease.get("scope", []))
    excluded = set(lease.get("excluded_scope", []))
    required = {REQUIRED_DB_SCOPE, REQUIRED_CODE_SCOPE}
    if not required.issubset(scope) or "database-writes" in excluded:
        raise ValueError("R15 apply Lease does not authorize exact code and database writes")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    plan = plan_internal_knowledge_seed(
        TenantScope(args.org, args.project),
        args.source.resolve(),
        observed_at=args.observed_at,
        freshness_expires_at=args.freshness_expires_at,
        now=args.now,
        expected_hash=args.expected_hash,
    )
    print(json.dumps(plan.model_dump(mode="json", by_alias=True), ensure_ascii=False, indent=2))
    if plan.status != "ready":
        return 2
    if args.apply:
        try:
            _require_apply_lease(args)
            content = args.source.resolve().read_text(encoding="utf-8")
            result = apply_internal_knowledge_seed(
                TenantScope(args.org, args.project),
                plan,
                content=content,
                actor=args.actor,
                reviewer=args.reviewer,
                occurred_at=args.now,
            )
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"R15_APPLY_BLOCKED: {exc}", file=sys.stderr)
            return 3
        print(
            json.dumps(
                result.model_dump(mode="json", by_alias=True),
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

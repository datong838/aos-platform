#!/usr/bin/env python3
"""Create a secret-free, read-only R33 authority snapshot for both tenants."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


COUNT_TABLES = (
    "aip_agent_instance",
    "aip_skill_binding",
    "aip_capability_binding",
    "aip_agent_run",
    "aip_provider_instance_head",
    "aip_registered_model_head",
    "aip_runtime_policy_head",
    "aip_model_route_head",
    "aip_provider_health_observation",
    "aip_model_capacity_pool_head",
    "aip_model_price_snapshot_head",
    "aip_budget_head",
    "aip_runtime_guard_policy_head",
    "aip_model_governance_policy_head",
    "aip_network_policy_head",
    "aip_eval_suite",
    "aip_eval_report_revision",
    "aip_memory_item",
    "aip_memory_pipeline_schedule",
    "aip_memory_pipeline_run",
    "wiki_page",
)

REQUIRED_OPERATIONAL_GATES = (
    "negativeCanaryIsolated",
    "sourceReadiness12of12",
    "sixAgentsRunnable",
)

OPERATIONAL_BLOCKED_EXIT_CODE = 3


def _value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _source_summary(envelope: Any) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    failures: list[dict[str, Any]] = []
    for item in envelope.sources:
        status = _value(item.status)
        status_counts[status] = status_counts.get(status, 0) + 1
        if status != "ready":
            failures.append(
                {
                    "pipelineId": item.pipeline_id,
                    "objectType": item.object_type,
                    "status": status,
                    "latestRunStatus": _value(item.latest_run.status),
                    "latestRunErrorCode": item.latest_run.error_code,
                    "dataCutoff": item.data_cutoff.isoformat() if item.data_cutoff else None,
                    "reasons": list(item.reasons),
                    "blockers": list(item.blockers),
                }
            )
    return {
        "checkedAt": envelope.checked_at.isoformat(),
        "cutoffAt": envelope.cutoff_at.isoformat(),
        "status": _value(envelope.status),
        "sourceCount": len(envelope.sources),
        "statusCounts": dict(sorted(status_counts.items())),
        "failures": failures,
        "receiptRef": envelope.receipt_ref.model_dump(mode="json", by_alias=True)
        if envelope.receipt_ref
        else None,
    }


def _agent_summary(runtime: Any) -> dict[str, Any]:
    blocked = []
    for item in runtime.catalog.items:
        if item.runtime_readiness != "runnable":
            blocked.append(
                {
                    "templateId": item.template.template_id,
                    "displayName": item.template.display_name,
                    "runtimeReadiness": item.runtime_readiness,
                    "blockerCodes": sorted(item.blockers),
                }
            )
    return {
        "evaluatedAt": runtime.evaluated_at.isoformat(),
        "stats": runtime.catalog.stats.model_dump(mode="json", by_alias=True),
        "bindingStats": runtime.binding_stats.model_dump(mode="json", by_alias=True),
        "blockedRoles": blocked,
    }


def _database_counts(scope: Any) -> dict[str, Any]:
    from aos_api.db import connect
    from aos_api.tenant_scope import apply_transaction_scope

    with connect() as conn:
        conn.rollback()
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        apply_transaction_scope(conn, scope)
        counts: dict[str, int] = {}
        for table in COUNT_TABLES:
            exists = conn.execute("SELECT to_regclass(%s) AS name", (f"public.{table}",)).fetchone()
            if not exists or not exists["name"]:
                counts[table] = -1
                continue
            row = conn.execute(
                f"SELECT count(*) AS count FROM {table} WHERE org_id=%s AND project_id=%s",
                scope.key,
            ).fetchone()
            counts[table] = int(row["count"])
        fresh_health = conn.execute(
            """SELECT count(*) AS count FROM aip_provider_health_observation
               WHERE org_id=%s AND project_id=%s AND expires_at>NOW()""",
            scope.key,
        ).fetchone()
        fresh_skill_bindings = conn.execute(
            """SELECT count(*) AS count FROM aip_skill_binding
               WHERE org_id=%s AND project_id=%s AND status='active'
                 AND readiness='available' AND readiness_expires_at>NOW()""",
            scope.key,
        ).fetchone()
        fresh_capability_bindings = conn.execute(
            """SELECT count(*) AS count FROM aip_capability_binding
               WHERE org_id=%s AND project_id=%s AND status='active'
                 AND operational_readiness='available' AND readiness_expires_at>NOW()""",
            scope.key,
        ).fetchone()
    return {
        "observedAt": datetime.now(UTC).isoformat(),
        "tableCounts": counts,
        "freshProviderHealthCount": int(fresh_health["count"]),
        "freshSkillBindingCount": int(fresh_skill_bindings["count"]),
        "freshCapabilityBindingCount": int(fresh_capability_bindings["count"]),
    }


def classify_gates(*, positive: dict[str, Any], negative: dict[str, Any]) -> dict[str, bool]:
    """Classify only the three R33 gates that this read-only snapshot can prove."""
    negative_counts = negative["authorityCounts"]["tableCounts"]
    return {
        "negativeCanaryIsolated": (
            negative["sourceReadiness"]["statusCounts"].get("ready", 0) == 0
            and negative["agentRuntime"]["stats"]["installedCount"] == 0
            and negative["agentRuntime"]["stats"]["runnableCount"] == 0
            and negative_counts["aip_agent_instance"] == 0
            and negative_counts["aip_skill_binding"] == 0
            and negative_counts["aip_capability_binding"] == 0
        ),
        "sourceReadiness12of12": (
            positive["sourceReadiness"]["sourceCount"] == 12
            and positive["sourceReadiness"]["statusCounts"].get("ready", 0) == 12
        ),
        "sixAgentsRunnable": (
            positive["agentRuntime"]["stats"]["definitionCount"] == 6
            and positive["agentRuntime"]["stats"]["installedCount"] == 6
            and positive["agentRuntime"]["stats"]["runnableCount"] == 6
        ),
    }


def classify_verdict(gates: dict[str, bool]) -> str:
    """Promote only an exact all-green operational gate set."""
    if all(gates.get(name) is True for name in REQUIRED_OPERATIONAL_GATES):
        return "OPERATIONAL_GREEN"
    return "CODE_API_GREEN_OPERATIONAL_BLOCKED"


def operational_gate_exit_code(*, verdict: str, require_operational_green: bool) -> int:
    """Keep evidence collection compatible while offering an explicit strict gate."""
    if require_operational_green and verdict != "OPERATIONAL_GREEN":
        return OPERATIONAL_BLOCKED_EXIT_CODE
    return 0


def snapshot_consistency() -> dict[str, Any]:
    """Describe the real transaction boundary without claiming cross-source atomicity."""
    return {
        "atomicAcrossAuthorities": False,
        "atomicAcrossTenants": False,
        "sourceReadiness": "SERVICE_SCOPED_READ_ONLY_SNAPSHOT",
        "agentRuntime": "INDEPENDENT_READ_ONLY_EVALUATION",
        "authorityCounts": "TENANT_SCOPED_REPEATABLE_READ",
        "decisionRule": "FAIL_CLOSED_CURRENT_OBSERVATIONS",
    }


def build_snapshot(*, checked_at: str) -> dict[str, Any]:
    from aos_api.aip_ecommerce_agent_installer import AipEcommerceAgentInstaller
    from aos_api.auth import Principal
    from aos_api.source_readiness import build_source_readiness_service
    from aos_api.tenant_scope import TenantScope

    service = build_source_readiness_service()
    installer = AipEcommerceAgentInstaller()
    tenants: dict[str, Any] = {}
    for org_id in ("org-org", "dev-org"):
        project_id = "dev-project"
        principal = Principal(
            subject="r33-readonly-auditor",
            org_id=org_id,
            project_id=project_id,
            roles=["developer"],
        )
        scope = TenantScope(org_id, project_id)
        tenants[f"{org_id}/{project_id}"] = {
            "sourceReadiness": _source_summary(
                service.read(org_id=org_id, project_id=project_id)
            ),
            "agentRuntime": _agent_summary(installer.runtime_readiness(principal)),
            "authorityCounts": _database_counts(scope),
        }

    positive = tenants["org-org/dev-project"]
    negative = tenants["dev-org/dev-project"]
    gates = classify_gates(positive=positive, negative=negative)
    return {
        "schemaVersion": "aip.r33.authority-snapshot.v1",
        "checkedAt": checked_at,
        "mode": "MULTI_AUTHORITY_READ_ONLY_SECRET_FREE",
        "consistency": snapshot_consistency(),
        "positiveTenant": "org-org/dev-project",
        "negativeCanary": "dev-org/dev-project",
        "verdict": classify_verdict(gates),
        "gates": gates,
        "tenants": tenants,
        "forbiddenData": {
            "secretPayloadRead": False,
            "sourcePayloadRead": False,
            "providerCall": False,
            "databaseWrite": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--checked-at", default=datetime.now(UTC).isoformat())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--require-operational-green",
        action="store_true",
        help="exit 3 after writing the snapshot when the operational verdict is not GREEN",
    )
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    sys.path.insert(0, str(repo_root / "services" / "aos-api"))
    snapshot = build_snapshot(checked_at=args.checked_at)
    if not snapshot["gates"]["negativeCanaryIsolated"]:
        raise RuntimeError("negative tenant isolation gate failed")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"verdict": snapshot["verdict"], "gates": snapshot["gates"]}, ensure_ascii=False))
    return operational_gate_exit_code(
        verdict=snapshot["verdict"],
        require_operational_green=args.require_operational_green,
    )


if __name__ == "__main__":
    raise SystemExit(main())

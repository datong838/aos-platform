"""Read-only Content-1 composition gate; never invokes Provider or writes Draft."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from aos_api.aip_content_contracts import (
    ContentDraftReadinessDecision,
    ContentDraftReadinessRequest,
)
from aos_api.aip_budget_contracts import BudgetLifecycle
from aos_api.aip_budget_store import AipBudgetAuthorityStore, BudgetNotFound, BudgetStoreError
from aos_api.aip_model_runtime_contracts import ModelRuntimeReadiness
from aos_api.aip_model_runtime_resolver import AipModelRuntimeResolver
from aos_api.aip_production_contracts import ContractBlocker, ContractReadiness, ExactRevisionRef
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


class AipContentDraftReadinessService:
    def __init__(self, connect_factory=None, *, model_resolver=None, budget_store=None) -> None:
        self._connect = connect_factory or connect
        self._resolver = model_resolver or AipModelRuntimeResolver()
        self._budget_store = budget_store or AipBudgetAuthorityStore(connect_factory or connect)

    def evaluate(
        self,
        scope: TenantScope,
        body: ContentDraftReadinessRequest,
    ) -> ContentDraftReadinessDecision:
        blockers: list[ContractBlocker] = []
        snapshot: list[dict[str, Any]] = []
        with self._connect(scope) as conn:
            for table, column, ref, scoped in (
                ("aip_task_brief_revision", "brief_id", body.brief_ref, True),
                ("aip_stage_template_revision", "template_id", body.pipeline.stage_template_ref, True),
                ("aip_responsibility_plan_revision", "plan_id", body.pipeline.responsibility_plan_ref, True),
                ("aip_eval_contract_revision", "contract_id", body.pipeline.eval_contract_ref, True),
                *[("aip_capability_revision", "capability_id", ref, False) for ref in body.pipeline.capability_refs],
            ):
                params = (*scope.key, ref.resource_id, ref.revision) if scoped else (ref.resource_id, ref.revision)
                tenant_where = "org_id=%s AND project_id=%s AND " if scoped else ""
                row = conn.execute(
                    f"SELECT revision,content_hash FROM {table} "
                    f"WHERE {tenant_where}{column}=%s AND revision=%s",
                    params,
                ).fetchone()
                self._exact(ref, row, snapshot, blockers)
            task_run = conn.execute(
                "SELECT version,status FROM aip_task_run "
                "WHERE org_id=%s AND project_id=%s AND run_id=%s",
                (*scope.key, body.task_run_ref.resource_id),
            ).fetchone()
            self._runtime("TaskRun", body.task_run_ref, task_run, snapshot, blockers)
            agent_run = conn.execute(
                "SELECT version,status,task_run_id,model_route_ref,policy_ref "
                "FROM aip_agent_run WHERE org_id=%s AND project_id=%s "
                "AND agent_run_id=%s",
                (*scope.key, body.agent_run_ref.resource_id),
            ).fetchone()
            self._runtime("AgentRun", body.agent_run_ref, agent_run, snapshot, blockers)
            if agent_run:
                snapshot.append(
                    {
                        "kind": "AgentRunBinding",
                        "taskRunId": agent_run["task_run_id"],
                        "route": agent_run["model_route_ref"],
                        "policy": agent_run["policy_ref"],
                    }
                )
                if agent_run["task_run_id"] != body.task_run_ref.resource_id:
                    blockers.append(self._block("CONTENT_DRAFT_RUN_BINDING_DRIFTED", "AgentRun does not belong to TaskRun"))
                if agent_run["status"] != "running":
                    blockers.append(self._block("CONTENT_DRAFT_AGENT_NOT_RUNNABLE", "AgentRun is not running"))
                route = body.pipeline.model_route_ref.model_dump(mode="json", by_alias=True) if body.pipeline.model_route_ref else None
                policy = body.pipeline.runtime_policy_ref.model_dump(mode="json", by_alias=True) if body.pipeline.runtime_policy_ref else None
                if route != agent_run["model_route_ref"] or policy != agent_run["policy_ref"]:
                    blockers.append(self._block("CONTENT_DRAFT_RUNTIME_REF_DRIFTED", "AgentRun route or policy differs from pipeline"))
        if body.pipeline.readiness is not ContractReadiness.READY:
            blockers.extend(body.pipeline.blockers)
        self._budget(body.pipeline.budget_ref, scope, snapshot, blockers)
        if body.pipeline.model_route_ref is None:
            blockers.append(self._block("CONTENT_DRAFT_MODEL_ROUTE_UNAVAILABLE", "exact ModelRouteRevision is required"))
        else:
            try:
                resolved = self._resolver.resolve(scope, body.pipeline.model_route_ref.resource_id)
                snapshot.append(
                    {
                        "kind": "ModelRuntimeResolution",
                        "readiness": resolved.readiness.value,
                        "blockers": resolved.blocker_codes,
                    }
                )
                if resolved.readiness is not ModelRuntimeReadiness.READY:
                    blockers.extend(
                        self._block(code, code)
                        for code in resolved.blocker_codes
                        or ["model_runtime_not_ready"]
                    )
            except Exception:
                blockers.append(self._block("CONTENT_DRAFT_MODEL_RUNTIME_UNAVAILABLE", "model runtime authority is unavailable"))
        blockers = self._dedupe(blockers)
        return ContentDraftReadinessDecision(
            tenant={"orgId": scope.org_id, "projectId": scope.project_id},
            readiness=(
                ContractReadiness.READY if not blockers else ContractReadiness.BLOCKED
            ),
            requestHash=self._hash(body.model_dump(mode="json", by_alias=True)),
            dependencySnapshotHash=self._hash(snapshot),
            blockers=blockers,
            evaluatedAt=datetime.now(timezone.utc),
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _budget(self, ref, scope, snapshot, blockers) -> None:
        if ref is None:
            blockers.append(
                self._block(
                    "CONTENT_DRAFT_BUDGET_AUTHORITY_UNAVAILABLE",
                    "exact BudgetRevision is required",
                )
            )
            return
        try:
            budget = self._budget_store.get(scope, ref.resource_id, ref.revision)
        except BudgetNotFound:
            blockers.append(
                self._block(
                    "CONTENT_DRAFT_BUDGET_AUTHORITY_UNAVAILABLE",
                    "BudgetRevision exact authority was not found",
                    ref,
                )
            )
            return
        except BudgetStoreError:
            blockers.append(
                self._block(
                    "CONTENT_DRAFT_BUDGET_AUTHORITY_UNAVAILABLE",
                    "BudgetRevision canonical authority is unavailable",
                    ref,
                )
            )
            return
        except Exception:
            blockers.append(
                self._block(
                    "CONTENT_DRAFT_BUDGET_AUTHORITY_UNAVAILABLE",
                    "BudgetRevision canonical authority is unavailable",
                    ref,
                )
            )
            return
        snapshot.append(
            {
                "kind": "BudgetRevision",
                "id": budget.budget_id,
                "expectedRevision": ref.revision,
                "expectedHash": ref.content_hash,
                "observedRevision": budget.revision,
                "observedHash": budget.content_hash,
                "lifecycle": budget.lifecycle.value,
                "effectiveFrom": budget.effective_from,
                "effectiveUntil": budget.effective_until,
            }
        )
        if budget.content_hash != ref.content_hash:
            blockers.append(self._block("CONTENT_DRAFT_BUDGET_REF_DRIFTED", "BudgetRevision exact ref drifted", ref))
        if budget.lifecycle is not BudgetLifecycle.ACTIVE:
            blockers.append(self._block("CONTENT_DRAFT_BUDGET_INACTIVE", "BudgetRevision is not active", ref))
        now = self._now()
        if not (budget.effective_from <= now < budget.effective_until):
            blockers.append(self._block("CONTENT_DRAFT_BUDGET_OUTSIDE_EFFECTIVE_WINDOW", "BudgetRevision is outside its effective window", ref))
        if not budget.hard_stop or budget.unknown_usage_behavior != "block":
            blockers.append(self._block("CONTENT_DRAFT_BUDGET_POLICY_UNSAFE", "BudgetRevision does not fail closed", ref))
        blockers.append(
            self._block(
                "CONTENT_DRAFT_BUDGET_BALANCE_AUTHORITY_UNAVAILABLE",
                "Budget usage and remaining balance authority are not available",
                ref,
            )
        )

    @staticmethod
    def _exact(ref: ExactRevisionRef, row: Any, snapshot: list[dict[str, Any]], blockers: list[ContractBlocker]) -> None:
        snapshot.append(
            {
                "kind": ref.resource_type,
                "id": ref.resource_id,
                "expectedRevision": ref.revision,
                "expectedHash": ref.content_hash,
                "observed": None
                if row is None
                else {
                    "revision": int(row["revision"]),
                    "contentHash": row["content_hash"],
                },
            }
        )
        if row is None:
            blockers.append(
                AipContentDraftReadinessService._block(
                    "CONTENT_DRAFT_DEPENDENCY_NOT_FOUND",
                    f"{ref.resource_type} not found",
                    ref,
                )
            )
        elif row["content_hash"] != ref.content_hash:
            blockers.append(
                AipContentDraftReadinessService._block(
                    "CONTENT_DRAFT_DEPENDENCY_DRIFTED",
                    f"{ref.resource_type} exact ref drifted",
                    ref,
                )
            )

    @staticmethod
    def _runtime(kind: str, ref: Any, row: Any, snapshot: list[dict[str, Any]], blockers: list[ContractBlocker]) -> None:
        snapshot.append(
            {
                "kind": kind,
                "id": ref.resource_id,
                "expectedVersion": ref.revision,
                "observedVersion": None if row is None else str(row["version"]),
                "status": None if row is None else row["status"],
            }
        )
        if row is None:
            blockers.append(
                AipContentDraftReadinessService._block(
                    "CONTENT_DRAFT_DEPENDENCY_NOT_FOUND", f"{kind} not found"
                )
            )
        elif str(row["version"]) != ref.revision:
            blockers.append(
                AipContentDraftReadinessService._block(
                    "CONTENT_DRAFT_DEPENDENCY_DRIFTED", f"{kind} version drifted"
                )
            )

    @staticmethod
    def _block(code: str, message: str, ref: ExactRevisionRef | None = None) -> ContractBlocker:
        return ContractBlocker(code=code, message=message, resource_ref=ref)

    @staticmethod
    def _dedupe(items: list[ContractBlocker]) -> list[ContractBlocker]:
        result: list[ContractBlocker] = []
        seen: set[tuple[str, str]] = set()
        for item in items:
            key = (item.code, item.message)
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result

    @staticmethod
    def _hash(value: Any) -> str:
        canonical = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode()
        return hashlib.sha256(canonical).hexdigest()

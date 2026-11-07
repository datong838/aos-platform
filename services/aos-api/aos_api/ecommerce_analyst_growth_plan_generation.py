"""Trusted D03 stage composition over the existing governed AgentRun executor.

The caller owns canonical task scheduling and supplies an already governed run.
No public route, run creation, implicit model choice or approval is introduced.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from pydantic import Field

from aos_api.aip_contracts import AipContractModel, ResourceRef
from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_agent_registry_store import AipAgentRegistryNotFound
from aos_api.aip_agent_run_execution_service import AipAgentRunExecutionService
from aos_api.aip_agent_run_execution_contracts import ExecuteAgentRunRequest
from aos_api.aip_agent_run_service import AipAgentRunService
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
from aos_api.ecommerce_analyst_authority_store import canonical_hash
from aos_api.ecommerce_analyst_growth_plan_draft import growth_plan_prompt
from aos_api.ecommerce_analyst_growth_plan_receiver import GrowthPlanDraftReceiver
from aos_api.ecommerce_analyst_growth_plan_sources import require_growth_plan_sources
from aos_api.tenant_scope import TenantScope


class GrowthPlanGenerationCommand(AipContractModel):
    expected_agent_run_version: int = Field(ge=1)
    attempt_id: str = Field(min_length=1, max_length=200)
    attempt_no: int = Field(ge=1)
    budget_ref: VersionedAssetRef
    capacity_reservation_ref: ResourceRef
    decision_ref: AnalystExactRef
    plan_budget: str = Field(pattern=r"^(0|[1-9][0-9]*)([.][0-9]{1,6})?$")
    task_type: str = Field(min_length=1, max_length=100)
    data_classification: Literal["public", "internal", "confidential"]


class GrowthPlanGenerationService:
    def __init__(self, connect_factory, executor):
        if not callable(connect_factory) or getattr(executor, "retains_output_text", False) is not True:
            raise ValueError("explicit scoped storage and retained-output executor required")
        self._connect = connect_factory
        self._executor = executor
        self._attempts = AipAgentRunExecutionService(connect_factory)
        self._runs = AipAgentRunService(connect_factory)
        self._receiver = GrowthPlanDraftReceiver(connect_factory)

    def generate(self, scope: TenantScope, agent_run_id: str, command: GrowthPlanGenerationCommand, *,
                 actor: str, markings: list[str], now: datetime, max_source_age: timedelta) -> AnalystExactRef:
        if not actor.strip() or command.data_classification not in markings:
            raise ValueError("explicit actor and classification access required")
        if command.decision_ref.resource_type != "DecisionSummaryRevision":
            raise ValueError("exact decision required")
        recovery = dict(attempt_id=command.attempt_id, decision_ref=command.decision_ref,
                        budget=command.plan_budget, task_type=command.task_type, actor=actor,
                        markings=markings, now=now, max_source_age=max_source_age)
        try:
            existing = self._attempts.get(scope, command.attempt_id)
        except AipAgentRegistryNotFound:
            existing = None
        if existing is not None:
            if ((existing.tenant.org_id, existing.tenant.project_id) != scope.key
                    or existing.agent_run_id != agent_run_id or existing.attempt_id != command.attempt_id
                    or existing.agent_run_version != command.expected_agent_run_version
                    or existing.attempt_no != command.attempt_no or existing.budget_ref != command.budget_ref
                    or existing.capacity_reservation_ref != command.capacity_reservation_ref
                    or existing.data_classification != command.data_classification or existing.created_by != actor):
                raise ValueError("generation attempt command drifted")
            if existing.status != "succeeded":
                raise ValueError("existing generation cannot be automatically reinvoked")
            return self._receiver.recover(scope, **recovery)
        run = self._runs.get(scope, agent_run_id)
        if ((run.tenant.org_id, run.tenant.project_id) != scope.key or run.agent_run_id != agent_run_id
                or run.status != "running" or run.version != command.expected_agent_run_version
                or run.request.skill.asset_type != "SkillTemplate" or run.request.skill.asset_id != "ecommerce.skill.D03"):
            raise ValueError("current running D03 AgentRun required")
        with self._connect(scope) as conn:
            if not conn.execute("SELECT to_regclass('public.aip_agent_text_output') AS storage").fetchone()["storage"]:
                raise ValueError("retained output storage migration is not deployed")
            decision = require_growth_plan_sources(conn, scope, command.decision_ref, markings=markings,
                                                    now=now, max_source_age=max_source_age)
            inputs = {(ref.resource_type, ref.resource_id, ref.revision, ref.authority) for ref in run.request.input_refs}
            required = {(ref.resource_type, ref.resource_id, str(ref.revision), "postgresql")
                        for ref in [command.decision_ref, decision.insight_ref, *decision.evidence_refs]}
            if not required.issubset(inputs):
                raise ValueError("D03 run lacks exact planning inputs")
            query, system = growth_plan_prompt(decision, budget=command.plan_budget, task_type=command.task_type)
        request = ExecuteAgentRunRequest(expectedAgentRunVersion=command.expected_agent_run_version,
            attemptId=command.attempt_id, attemptNo=command.attempt_no, budgetRef=command.budget_ref,
            capacityReservationRef=command.capacity_reservation_ref, query=query, systemPrompt=system,
            dataClassification=command.data_classification)
        key = "growth-generate:" + canonical_hash({"tenant": scope.key, "attemptId": command.attempt_id})
        result = self._executor.execute(scope, agent_run_id, request, idempotency_key=key, actor=actor, occurred_at=now)
        if result.attempt.status != "succeeded":
            raise ValueError("generation did not produce a recoverable successful output")
        return self._receiver.recover(scope, **recovery)

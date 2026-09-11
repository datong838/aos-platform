"""Internal sourced D01 composition over the governed retained-output executor."""
from datetime import datetime, timedelta
from typing import Literal

from pydantic import Field

from aos_api.aip_contracts import AipContractModel, ResourceRef
from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_agent_registry_store import AipAgentRegistryNotFound
from aos_api.aip_agent_run_execution_service import AipAgentRunExecutionService
from aos_api.aip_agent_run_execution_contracts import ExecuteAgentRunRequest
from aos_api.aip_agent_run_service import AipAgentRunService
from aos_api.ecommerce_analyst_portrait_inputs import PortraitMetricSourceRequest, read_portrait_inputs
from aos_api.ecommerce_analyst_diagnosis_service import require_source_classification
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
from aos_api.ecommerce_analyst_authority_store import canonical_hash
from aos_api.ecommerce_analyst_portrait_generation import portrait_prompt
from aos_api.ecommerce_analyst_portrait_receiver import PortraitReceiver
from aos_api.tenant_scope import TenantScope


class PortraitGenerationCommand(AipContractModel):
    expected_agent_run_version: int = Field(ge=1)
    attempt_id: str = Field(min_length=1, max_length=200)
    attempt_no: int = Field(ge=1)
    budget_ref: VersionedAssetRef
    capacity_reservation_ref: ResourceRef
    method_ref: AnalystExactRef
    eval_ref: AnalystExactRef
    cutoff_at: datetime
    metric_sources: list[PortraitMetricSourceRequest] = Field(min_length=1, max_length=100)
    data_classification: Literal["public", "internal", "confidential"]


class PortraitGenerationService:
    def __init__(self, connect_factory, executor):
        if not callable(connect_factory) or getattr(executor, "retains_output_text", False) is not True:
            raise ValueError("explicit scoped storage and retained-output executor required")
        self._connect = connect_factory
        self._executor = executor
        self._attempts = AipAgentRunExecutionService(connect_factory)
        self._runs = AipAgentRunService(connect_factory)
        self._receiver = PortraitReceiver(connect_factory)

    def generate(self, scope: TenantScope, agent_run_id: str, command: PortraitGenerationCommand, *,
                 actor: str, markings: list[str], clock, max_source_age: timedelta, max_bytes: int) -> AnalystExactRef:
        command = PortraitGenerationCommand.model_validate(command.model_dump(mode="python"))
        markings = list(markings)
        if (not actor.strip() or command.data_classification not in markings or not callable(clock)
                or command.method_ref.resource_type != "MethodRevision" or command.eval_ref.resource_type != "EvalContractRevision"
                or max_source_age <= timedelta(0) or type(max_bytes) is not int or max_bytes <= 0):
            raise ValueError("explicit portrait identity, classification, clock and source limits required")
        def current_time():
            value = clock()
            if not isinstance(value, datetime) or value.utcoffset() is None:
                raise ValueError("aware current clock required")
            return value
        recovery = dict(attempt_id=command.attempt_id, method_ref=command.method_ref, eval_ref=command.eval_ref, cutoff_at=command.cutoff_at,
            metric_sources=command.metric_sources, actor=actor, markings=markings,
            max_source_age=max_source_age, max_bytes=max_bytes)
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
                raise ValueError("portrait generation attempt command drifted")
            if existing.status != "succeeded":
                raise ValueError("existing portrait generation cannot be automatically reinvoked")
            return self._receiver.recover(scope, **recovery, now=current_time())
        run = self._runs.get(scope, agent_run_id)
        if ((run.tenant.org_id, run.tenant.project_id) != scope.key or run.agent_run_id != agent_run_id
                or run.status != "running" or run.version != command.expected_agent_run_version
                or run.request.skill.asset_type != "SkillTemplate" or run.request.skill.asset_id != "ecommerce.skill.D01"):
            raise ValueError("current running D01 AgentRun required")
        with self._connect(scope) as conn:
            if not conn.execute("SELECT to_regclass('public.aip_agent_text_output') AS storage").fetchone()["storage"]:
                raise ValueError("retained output storage migration is not deployed")
            inputs = read_portrait_inputs(conn=conn, scope=scope, method_ref=command.method_ref, eval_ref=command.eval_ref,
                metric_sources=command.metric_sources, cutoff_at=command.cutoff_at, run=run, actor=actor, markings=markings,
                now=current_time(), max_source_age=max_source_age, max_bytes=max_bytes)
            require_source_classification(inputs['materials'], command.data_classification)
            query, system = portrait_prompt(**inputs)
        request = ExecuteAgentRunRequest(expectedAgentRunVersion=command.expected_agent_run_version,
            attemptId=command.attempt_id, attemptNo=command.attempt_no, budgetRef=command.budget_ref,
            capacityReservationRef=command.capacity_reservation_ref, query=query, systemPrompt=system,
            dataClassification=command.data_classification)
        key = "portrait-generate:" + canonical_hash({"tenant": scope.key, "attemptId": command.attempt_id})
        result = self._executor.execute(scope, agent_run_id, request, idempotency_key=key, actor=actor, occurred_at=current_time())
        if result.attempt.status != "succeeded":
            raise ValueError("portrait generation did not produce a recoverable successful output")
        return self._receiver.recover(scope, **recovery, now=current_time())

"""Internal sourced D02 composition over the governed retained-output executor."""
from datetime import datetime, timedelta
from typing import Literal

from pydantic import Field

from aos_api.aip_contracts import AipContractModel, ResourceRef
from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_agent_registry_store import AipAgentRegistryNotFound
from aos_api.aip_agent_run_execution_service import AipAgentRunExecutionService
from aos_api.aip_agent_run_execution_contracts import ExecuteAgentRunRequest
from aos_api.aip_agent_run_service import AipAgentRunService
from aos_api.ecommerce_analyst_analysis_sources import AnalysisBundleSourceRequest
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
from aos_api.ecommerce_analyst_authority_store import canonical_hash
from aos_api.ecommerce_analyst_diagnosis_generation import diagnosis_prompt
from aos_api.ecommerce_analyst_diagnosis_receiver import DiagnosisReceiver, read_diagnosis_inputs
from aos_api.tenant_scope import TenantScope


class DiagnosisGenerationCommand(AipContractModel):
    expected_agent_run_version: int = Field(ge=1)
    attempt_id: str = Field(min_length=1, max_length=200)
    attempt_no: int = Field(ge=1)
    budget_ref: VersionedAssetRef
    capacity_reservation_ref: ResourceRef
    insight_ref: AnalystExactRef
    source_requests: list[AnalysisBundleSourceRequest] = Field(min_length=1, max_length=100)
    data_classification: Literal["public", "internal", "confidential"]


def require_source_classification(materials, classification):
    """Reading raw evidence is not permission to downgrade it for model egress."""
    ranks = {"public": 0, "internal": 1, "confidential": 2}
    for material in materials:
        levels = [material.get("marking"), *[item["payload"].get("marking", ["public"]) for item in material["items"]]]
        for markings in levels:
            if (not isinstance(markings, list) or not markings
                    or any(not isinstance(value, str) or value not in ranks for value in markings)
                    or max(ranks[value] for value in markings) > ranks[classification]):
                raise ValueError("diagnosis source classification cannot be downgraded or inferred")


class DiagnosisGenerationService:
    def __init__(self, connect_factory, executor):
        if not callable(connect_factory) or getattr(executor, "retains_output_text", False) is not True:
            raise ValueError("explicit scoped storage and retained-output executor required")
        self._connect = connect_factory
        self._executor = executor
        self._attempts = AipAgentRunExecutionService(connect_factory)
        self._runs = AipAgentRunService(connect_factory)
        self._receiver = DiagnosisReceiver(connect_factory)

    def generate(self, scope: TenantScope, agent_run_id: str, command: DiagnosisGenerationCommand, *,
                 actor: str, markings: list[str], clock, max_source_age: timedelta, max_bytes: int) -> AnalystExactRef:
        command = DiagnosisGenerationCommand.model_validate(command.model_dump(mode="python"))
        markings = list(markings)
        if (not actor.strip() or command.data_classification not in markings or not callable(clock)
                or command.insight_ref.resource_type != "InsightRevision"
                or max_source_age <= timedelta(0) or type(max_bytes) is not int or max_bytes <= 0):
            raise ValueError("explicit diagnosis identity, classification, clock and source limits required")
        def current_time():
            value = clock()
            if not isinstance(value, datetime) or value.utcoffset() is None:
                raise ValueError("aware current clock required")
            return value
        recovery = dict(attempt_id=command.attempt_id, insight_ref=command.insight_ref,
            source_requests=command.source_requests, actor=actor, markings=markings,
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
                raise ValueError("diagnosis generation attempt command drifted")
            if existing.status != "succeeded":
                raise ValueError("existing diagnosis generation cannot be automatically reinvoked")
            return self._receiver.recover(scope, **recovery, now=current_time())
        run = self._runs.get(scope, agent_run_id)
        if ((run.tenant.org_id, run.tenant.project_id) != scope.key or run.agent_run_id != agent_run_id
                or run.status != "running" or run.version != command.expected_agent_run_version
                or run.request.skill.asset_type != "SkillTemplate" or run.request.skill.asset_id != "ecommerce.skill.D02"):
            raise ValueError("current running D02 AgentRun required")
        with self._connect(scope) as conn:
            if not conn.execute("SELECT to_regclass('public.aip_agent_text_output') AS storage").fetchone()["storage"]:
                raise ValueError("retained output storage migration is not deployed")
            insight, materials = read_diagnosis_inputs(conn=conn, scope=scope, insight_ref=command.insight_ref,
                source_requests=command.source_requests, run=run, actor=actor, markings=markings,
                now=current_time(), max_source_age=max_source_age, max_bytes=max_bytes)
            require_source_classification(materials, command.data_classification)
            query, system = diagnosis_prompt(insight, materials)
        request = ExecuteAgentRunRequest(expectedAgentRunVersion=command.expected_agent_run_version,
            attemptId=command.attempt_id, attemptNo=command.attempt_no, budgetRef=command.budget_ref,
            capacityReservationRef=command.capacity_reservation_ref, query=query, systemPrompt=system,
            dataClassification=command.data_classification)
        key = "diagnosis-generate:" + canonical_hash({"tenant": scope.key, "attemptId": command.attempt_id})
        result = self._executor.execute(scope, agent_run_id, request, idempotency_key=key, actor=actor, occurred_at=current_time())
        if result.attempt.status != "succeeded":
            raise ValueError("diagnosis generation did not produce a recoverable successful output")
        return self._receiver.recover(scope, **recovery, now=current_time())

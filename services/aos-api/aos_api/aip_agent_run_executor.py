"""Canonical, single-attempt AgentRun execution composition.

The executor persists only hashes and exact authority references. Provider
prompt/answer text is transient and is never written to attempts, receipts or
logs by this layer.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any

from aos_api.aip_agent_registry_contracts import (
    AgentRun,
    AgentRunStatus,
    RegistryReceipt,
    VersionedAssetRef,
)
from aos_api.aip_agent_registry_store import AipAgentRegistryNotFound
from aos_api.aip_agent_run_execution_contracts import (
    AgentRunExecutionAttempt,
    AgentRunExecutionStatus,
    CreateAgentRunExecutionAttemptRequest,
    ExecuteAgentRunRequest,
    ExecuteAgentRunResponse,
    TransitionAgentRunExecutionAttemptRequest,
)
from aos_api.aip_agent_run_execution_service import AipAgentRunExecutionService
from aos_api.aip_agent_run_service import AipAgentRunService
from aos_api.aip_contracts import ArtifactRef, ResourceRef, TenantContext
from aos_api.aip_eval_contracts import LineageRootType
from aos_api.aip_lineage_service import AipLineageService
from aos_api.aip_llm_adapter import LLMAdapter, LLMRuntimeBlocked
from aos_api.aip_model_runtime_contracts import ModelRuntimeReadiness
from aos_api.aip_model_runtime_resolver import AipModelRuntimeResolver
from aos_api.aip_task_store import AipTaskStore
from aos_api.tenant_scope import TenantScope


class AipAgentRunExecutorError(RuntimeError):
    code = "AIP_AGENT_RUN_EXECUTION_BLOCKED"

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


_SAFE_PROVIDER_UNKNOWN_REASONS = {
    "provider_http_error": "PROVIDER_HTTP_ERROR",
    "provider_timeout": "PROVIDER_TIMEOUT",
    "provider_transport_error": "PROVIDER_TRANSPORT_ERROR",
    "provider_response_invalid": "PROVIDER_RESPONSE_INVALID",
    "provider_response_receipt_missing": "PROVIDER_RESPONSE_RECEIPT_MISSING",
    "provider_response_model_missing": "PROVIDER_RESPONSE_MODEL_MISSING",
    "provider_response_model_drifted": "PROVIDER_RESPONSE_MODEL_DRIFTED",
    "provider_response_answer_missing": "PROVIDER_RESPONSE_ANSWER_MISSING",
    "provider_response_usage_missing": "PROVIDER_RESPONSE_USAGE_MISSING",
    "provider_usage_unknown": "PROVIDER_USAGE_UNKNOWN",
    "provider_usage_authority_write_failed": "PROVIDER_USAGE_AUTHORITY_WRITE_FAILED",
    "provider_prompt_empty": "PROVIDER_PROMPT_EMPTY",
    "model_runtime_not_ready": "MODEL_RUNTIME_NOT_READY",
    "model_runtime_authority_unavailable": "MODEL_RUNTIME_AUTHORITY_UNAVAILABLE",
    "model_runtime_lifecycle_blocked": "MODEL_RUNTIME_LIFECYCLE_BLOCKED",
    "provider_tenant_mismatch": "PROVIDER_TENANT_MISMATCH",
    "runtime_policy_kill_switch": "RUNTIME_POLICY_KILL_SWITCH",
    "route_ref_drifted": "ROUTE_REF_DRIFTED",
    "route_policy_ref_drifted": "ROUTE_POLICY_REF_DRIFTED",
    "route_model_ref_drifted": "ROUTE_MODEL_REF_DRIFTED",
    "model_ref_drifted": "MODEL_REF_DRIFTED",
    "provider_ref_drifted": "PROVIDER_REF_DRIFTED",
    "model_provider_ref_drifted": "MODEL_PROVIDER_REF_DRIFTED",
    "quota_policy_ref_drifted": "QUOTA_POLICY_REF_DRIFTED",
    "budget_policy_ref_drifted": "BUDGET_POLICY_REF_DRIFTED",
    "egress_policy_ref_drifted": "EGRESS_POLICY_REF_DRIFTED",
    "data_policy_ref_drifted": "DATA_POLICY_REF_DRIFTED",
    "provider_plugin_authority_blocked": "PROVIDER_PLUGIN_AUTHORITY_BLOCKED",
    "provider_plugin_capability_blocked": "PROVIDER_PLUGIN_CAPABILITY_BLOCKED",
    "runtime_guard_policy_blocked": "RUNTIME_GUARD_POLICY_BLOCKED",
    "data_classification_blocked": "DATA_CLASSIFICATION_BLOCKED",
    "provider_region_unconfirmed": "PROVIDER_REGION_UNCONFIRMED",
    "network_policy_blocked": "NETWORK_POLICY_BLOCKED",
    "model_governance_policy_blocked": "MODEL_GOVERNANCE_POLICY_BLOCKED",
    "provider_endpoint_blocked": "PROVIDER_ENDPOINT_BLOCKED",
    "provider_timeout_policy_blocked": "PROVIDER_TIMEOUT_POLICY_BLOCKED",
    "lineage_id_required": "LINEAGE_ID_REQUIRED",
    "data_classification_required": "DATA_CLASSIFICATION_REQUIRED",
    "exact_scope_and_model_route_required": "EXACT_SCOPE_AND_MODEL_ROUTE_REQUIRED",
    "implicit_mock_provider_forbidden": "IMPLICIT_MOCK_PROVIDER_FORBIDDEN",
}


_SAFE_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,120}$")


class AipAgentRunExecutor:
    def __init__(
        self,
        *,
        run_service: Any | None = None,
        attempt_service: Any | None = None,
        resolver: Any | None = None,
        llm_adapter: Any | None = None,
        artifact_store: Any | None = None,
        lineage_service: Any | None = None,
    ) -> None:
        self._run_service = run_service or AipAgentRunService()
        self._attempt_service = attempt_service or AipAgentRunExecutionService()
        self._resolver = resolver or AipModelRuntimeResolver()
        self._llm_adapter = llm_adapter or LLMAdapter()
        self._artifact_store = artifact_store or AipTaskStore()
        self._lineage_service = lineage_service or AipLineageService()

    def execute(
        self,
        scope: TenantScope,
        agent_run_id: str,
        request: ExecuteAgentRunRequest,
        *,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> ExecuteAgentRunResponse:
        request_hash = self._request_hash(agent_run_id, request)
        existing = self._existing_attempt(scope, request.attempt_id)
        if existing is not None:
            self._require_replay_matches(existing, agent_run_id, request, request_hash)
            attempt, receipt = self._replay_create(
                scope, existing, idempotency_key, actor, occurred_at
            )
            return self._resume_or_replay(
                scope, attempt, receipt, request, idempotency_key, actor, occurred_at
            )

        run = self._require_running_run(scope, agent_run_id, request.expected_agent_run_version)
        try:
            resolution = self._preflight(scope, run)
        except Exception:
            self._align_run_terminal(
                scope, run.agent_run_id, AgentRunStatus.FAILED, actor, occurred_at
            )
            raise
        lineage_id = self._lineage_service.lineage_id(
            LineageRootType.TASK_RUN, run.task_run_id
        )
        attempt_request = CreateAgentRunExecutionAttemptRequest(
            attemptId=request.attempt_id,
            agentRunRef=self._run_ref(run),
            attemptNo=request.attempt_no,
            routeRef=resolution.route,
            policyRef=resolution.policy,
            modelRef=resolution.selected_model,
            providerRef=resolution.selected_provider,
            priceSnapshotRef=resolution.selected_price_snapshot,
            budgetRef=request.budget_ref,
            capacityReservationRef=request.capacity_reservation_ref,
            dataClassification=request.data_classification,
            lineageId=lineage_id,
            requestHash=request_hash,
        )
        attempt, receipt = self._attempt_service.create(
            scope,
            attempt_request,
            idempotency_key=idempotency_key,
            actor=actor,
            occurred_at=occurred_at,
        )
        return self._invoke(
            scope, run, attempt, receipt, request, idempotency_key, actor, occurred_at
        )

    def _resume_or_replay(
        self,
        scope: TenantScope,
        attempt: AgentRunExecutionAttempt,
        receipt: RegistryReceipt,
        request: ExecuteAgentRunRequest,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> ExecuteAgentRunResponse:
        target = {
            AgentRunExecutionStatus.SUCCEEDED: AgentRunStatus.SUCCEEDED,
            AgentRunExecutionStatus.FAILED: AgentRunStatus.FAILED,
            AgentRunExecutionStatus.UNKNOWN: AgentRunStatus.UNKNOWN,
        }.get(attempt.status)
        if target is not None:
            run = self._align_run_terminal(scope, attempt.agent_run_id, target, actor, occurred_at)
            return self._response(scope, run, attempt, receipt, replayed=True)
        if attempt.status is AgentRunExecutionStatus.INVOKING:
            attempt, _ = self._attempt_service.transition(
                scope,
                attempt.attempt_id,
                TransitionAgentRunExecutionAttemptRequest(
                    expectedVersion=attempt.version,
                    fromStatus="invoking",
                    toStatus="unknown",
                    reasonCode="INVOCATION_OUTCOME_UNPROVEN",
                ),
                idempotency_key=f"{idempotency_key}:recover-unknown",
                actor=actor,
                occurred_at=occurred_at,
            )
            run = self._align_run_terminal(
                scope, attempt.agent_run_id, AgentRunStatus.UNKNOWN, actor, occurred_at
            )
            return self._response(scope, run, attempt, receipt, replayed=True)
        run = self._require_running_run(
            scope, attempt.agent_run_id, attempt.agent_run_version
        )
        return self._invoke(
            scope, run, attempt, receipt, request, idempotency_key, actor, occurred_at
        )

    def _invoke(
        self,
        scope: TenantScope,
        run: AgentRun,
        attempt: AgentRunExecutionAttempt,
        receipt: RegistryReceipt,
        request: ExecuteAgentRunRequest,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> ExecuteAgentRunResponse:
        try:
            attempt, _ = self._attempt_service.transition(
                scope,
                attempt.attempt_id,
                TransitionAgentRunExecutionAttemptRequest(
                    expectedVersion=attempt.version,
                    fromStatus="prepared",
                    toStatus="invoking",
                ),
                idempotency_key=f"{idempotency_key}:invoking",
                actor=actor,
                occurred_at=occurred_at,
            )
        except Exception as exc:
            self._align_run_terminal(
                scope, run.agent_run_id, AgentRunStatus.FAILED, actor, occurred_at
            )
            raise AipAgentRunExecutorError("ATTEMPT_INVOKING_COMMIT_FAILED") from exc

        response: dict[str, Any] | None = None
        artifact_ref: ArtifactRef | None = None
        lineage_count = 0
        failure_reason = "PROVIDER_RESULT_UNKNOWN"
        try:
            response = self._llm_adapter.chat_exact(
                scope,
                attempt.route_ref.asset_id,
                request.query,
                lineage_id=attempt.lineage_id,
                system_prompt=request.system_prompt,
                data_classification=request.data_classification,
            )
            failure_reason = "ARTIFACT_WRITE_FAILED"
            artifact_ref = self._record_output_artifact(scope, run, attempt, response, actor)
            failure_reason = "LINEAGE_RECONCILE_FAILED"
            lineage_count = len(
                self._lineage_service.reconcile(
                    scope, LineageRootType.TASK_RUN, run.task_run_id
                )
            )
            failure_reason = "ATTEMPT_SUCCESS_COMMIT_FAILED"
            attempt, _ = self._attempt_service.transition(
                scope,
                attempt.attempt_id,
                TransitionAgentRunExecutionAttemptRequest(
                    expectedVersion=attempt.version,
                    fromStatus="invoking",
                    toStatus="succeeded",
                    providerReceiptId=self._provider_receipt(response),
                    usageReceiptIds=self._usage_receipts(response),
                    outputArtifactRef=artifact_ref,
                ),
                idempotency_key=f"{idempotency_key}:succeeded",
                actor=actor,
                occurred_at=occurred_at,
            )
        except Exception as exc:
            if failure_reason == "PROVIDER_RESULT_UNKNOWN":
                failure_reason = self._safe_provider_unknown_reason(exc)
            try:
                attempt = self._mark_unknown(
                    scope,
                    attempt,
                    response,
                    artifact_ref,
                    failure_reason,
                    idempotency_key,
                    actor,
                    occurred_at,
                )
            except Exception as exc:
                self._align_run_terminal(
                    scope, run.agent_run_id, AgentRunStatus.UNKNOWN, actor, occurred_at
                )
                raise AipAgentRunExecutorError(
                    "ATTEMPT_UNKNOWN_COMMIT_FAILED"
                ) from exc
            run = self._align_run_terminal(
                scope, run.agent_run_id, AgentRunStatus.UNKNOWN, actor, occurred_at
            )
            return self._response(
                scope,
                run,
                attempt,
                receipt,
                replayed=False,
                lineage_event_count=lineage_count,
            )

        run = self._align_run_terminal(
            scope, run.agent_run_id, AgentRunStatus.SUCCEEDED, actor, occurred_at
        )
        return self._response(
            scope,
            run,
            attempt,
            receipt,
            answer=str(response["answer"]),
            replayed=False,
            lineage_event_count=lineage_count,
        )

    @staticmethod
    def _safe_provider_unknown_reason(exc: Exception) -> str:
        if not isinstance(exc, LLMRuntimeBlocked):
            return "PROVIDER_RESULT_UNKNOWN"
        code = str(getattr(exc, "code", "") or exc)
        if not _SAFE_CODE_PATTERN.fullmatch(code):
            # secret_* codes are stable prefixes without free-form payload.
            if code.startswith("secret_") and _SAFE_CODE_PATTERN.fullmatch(code[7:] or "x"):
                return f"SECRET_{code[7:].upper()}"
            return "PROVIDER_RESULT_UNKNOWN"
        mapped = _SAFE_PROVIDER_UNKNOWN_REASONS.get(code)
        if mapped is not None:
            return mapped
        return code.upper()

    def _mark_unknown(
        self,
        scope: TenantScope,
        attempt: AgentRunExecutionAttempt,
        response: dict[str, Any] | None,
        artifact_ref: ArtifactRef | None,
        reason_code: str,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> AgentRunExecutionAttempt:
        body = TransitionAgentRunExecutionAttemptRequest(
            expectedVersion=attempt.version,
            fromStatus="invoking",
            toStatus="unknown",
            providerReceiptId=self._provider_receipt(response, required=False),
            usageReceiptIds=self._usage_receipts(response, required=False),
            outputArtifactRef=artifact_ref,
            reasonCode=reason_code,
        )
        updated, _ = self._attempt_service.transition(
            scope,
            attempt.attempt_id,
            body,
            idempotency_key=f"{idempotency_key}:unknown:{reason_code.lower()}",
            actor=actor,
            occurred_at=occurred_at,
        )
        return updated

    def _record_output_artifact(
        self,
        scope: TenantScope,
        run: AgentRun,
        attempt: AgentRunExecutionAttempt,
        response: dict[str, Any],
        actor: str,
    ) -> ArtifactRef:
        answer = str(response["answer"])
        content_hash = hashlib.sha256(answer.encode("utf-8")).hexdigest()
        artifact_id = self._artifact_store.record_artifact(
            scope,
            run.task_run_id,
            actor,
            "agent_text_output",
            {
                "contentRef": f"sha256://{content_hash}",
                "schemaRef": "aos://schemas/aip-agent-text-output/v1",
                "contentHash": content_hash,
                "marking": [attempt.data_classification],
                "source": {
                    "agentRunId": run.agent_run_id,
                    "attemptId": attempt.attempt_id,
                    "providerReceiptId": self._provider_receipt(response),
                },
                "metadata": {
                    "answerLength": len(answer),
                    "usageReceiptIds": self._usage_receipts(response),
                },
            },
        )
        return ArtifactRef(
            artifactId=artifact_id,
            artifactType="agent_text_output",
            revision="1",
            contentHash=content_hash,
        )

    def _preflight(self, scope: TenantScope, run: AgentRun):
        resolution = self._resolver.resolve(scope, run.request.model_route.asset_id)
        if resolution.readiness is not ModelRuntimeReadiness.READY:
            raise AipAgentRunExecutorError(
                ",".join(resolution.blocker_codes) or "MODEL_RUNTIME_NOT_READY"
            )
        if resolution.route != run.request.model_route:
            raise AipAgentRunExecutorError("MODEL_ROUTE_EXACT_REF_DRIFTED")
        if resolution.policy != run.request.policy:
            raise AipAgentRunExecutorError("RUNTIME_POLICY_EXACT_REF_DRIFTED")
        if (
            resolution.selected_model is None
            or resolution.selected_provider is None
            or resolution.selected_price_snapshot is None
        ):
            raise AipAgentRunExecutorError("MODEL_RUNTIME_SELECTION_MISSING")
        return resolution

    def _require_running_run(
        self, scope: TenantScope, agent_run_id: str, expected_version: int
    ) -> AgentRun:
        run = self._run_service.get(scope, agent_run_id)
        if run.version != expected_version:
            raise AipAgentRunExecutorError("AGENT_RUN_VERSION_DRIFTED")
        if run.status is not AgentRunStatus.RUNNING:
            raise AipAgentRunExecutorError("AGENT_RUN_NOT_RUNNING")
        return run

    def _align_run_terminal(
        self,
        scope: TenantScope,
        agent_run_id: str,
        target: AgentRunStatus,
        actor: str,
        occurred_at: datetime,
    ) -> AgentRun:
        run = self._run_service.get(scope, agent_run_id)
        if run.status is target:
            return run
        if run.status is not AgentRunStatus.RUNNING:
            raise AipAgentRunExecutorError("AGENT_RUN_TERMINAL_DRIFTED")
        return self._run_service.transition(
            scope,
            agent_run_id,
            expected_version=run.version,
            from_status=AgentRunStatus.RUNNING,
            to_status=target,
            actor=actor,
            occurred_at=occurred_at,
        )

    def _existing_attempt(
        self, scope: TenantScope, attempt_id: str
    ) -> AgentRunExecutionAttempt | None:
        try:
            return self._attempt_service.get(scope, attempt_id)
        except AipAgentRegistryNotFound:
            return None

    def _replay_create(
        self,
        scope: TenantScope,
        attempt: AgentRunExecutionAttempt,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> tuple[AgentRunExecutionAttempt, RegistryReceipt]:
        return self._attempt_service.create(
            scope,
            CreateAgentRunExecutionAttemptRequest(
                attemptId=attempt.attempt_id,
                agentRunRef=ResourceRef(
                    resourceType="AgentRun",
                    resourceId=attempt.agent_run_id,
                    revision=str(attempt.agent_run_version),
                    authority="postgresql",
                ),
                attemptNo=attempt.attempt_no,
                routeRef=attempt.route_ref,
                policyRef=attempt.policy_ref,
                modelRef=attempt.model_ref,
                providerRef=attempt.provider_ref,
                priceSnapshotRef=attempt.price_snapshot_ref,
                budgetRef=attempt.budget_ref,
                capacityReservationRef=attempt.capacity_reservation_ref,
                dataClassification=attempt.data_classification,
                lineageId=attempt.lineage_id,
                requestHash=attempt.request_hash,
            ),
            idempotency_key=idempotency_key,
            actor=actor,
            occurred_at=occurred_at,
        )

    @staticmethod
    def _require_replay_matches(
        attempt: AgentRunExecutionAttempt,
        agent_run_id: str,
        request: ExecuteAgentRunRequest,
        request_hash: str,
    ) -> None:
        exact = (
            attempt.agent_run_id == agent_run_id
            and attempt.agent_run_version == request.expected_agent_run_version
            and attempt.attempt_no == request.attempt_no
            and attempt.budget_ref == request.budget_ref
            and attempt.capacity_reservation_ref == request.capacity_reservation_ref
            and attempt.data_classification == request.data_classification
            and attempt.request_hash == request_hash
        )
        if not exact:
            raise AipAgentRunExecutorError("EXECUTE_IDEMPOTENCY_PAYLOAD_DRIFTED")

    @staticmethod
    def _run_ref(run: AgentRun) -> ResourceRef:
        return ResourceRef(
            resourceType="AgentRun",
            resourceId=run.agent_run_id,
            revision=str(run.version),
            authority="postgresql",
        )

    @staticmethod
    def _request_hash(agent_run_id: str, request: ExecuteAgentRunRequest) -> str:
        payload = {
            "agentRunId": agent_run_id,
            **request.model_dump(mode="json", by_alias=True),
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _provider_receipt(
        response: dict[str, Any] | None, *, required: bool = True
    ) -> str | None:
        value = response.get("providerReceiptId") if response else None
        if isinstance(value, str) and value.strip():
            return value
        if required:
            raise AipAgentRunExecutorError("PROVIDER_RECEIPT_ID_REQUIRED")
        return None

    @staticmethod
    def _usage_receipts(
        response: dict[str, Any] | None, *, required: bool = True
    ) -> list[str]:
        values = response.get("usageReceiptIds") if response else None
        if isinstance(values, list) and values and all(
            isinstance(value, str) and value.strip() for value in values
        ):
            return values
        if required:
            raise AipAgentRunExecutorError("USAGE_RECEIPTS_REQUIRED")
        return []

    @staticmethod
    def _response(
        scope: TenantScope,
        run: AgentRun,
        attempt: AgentRunExecutionAttempt,
        receipt: RegistryReceipt,
        *,
        answer: str | None = None,
        replayed: bool,
        lineage_event_count: int = 0,
    ) -> ExecuteAgentRunResponse:
        return ExecuteAgentRunResponse(
            tenant=TenantContext(orgId=scope.org_id, projectId=scope.project_id),
            agentRun=run,
            attempt=attempt,
            attemptReceipt=receipt,
            answer=answer,
            replayed=replayed,
            lineageEventCount=lineage_event_count,
        )


__all__ = ["AipAgentRunExecutor", "AipAgentRunExecutorError"]

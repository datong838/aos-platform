"""Nine explicit trusted-host adapters for the ecommerce growth package."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import json
import math
import re
import unicodedata
from typing import Any, Mapping, Protocol
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

from aos_api.ecommerce_growth_host_ports import (
    DispatchAuthorityRef,
    EcommerceGrowthDispatchSnapshot,
    EcommerceGrowthOperationBinding,
    HostTransaction,
)
from aos_api.ecommerce_growth_runtime_store import BoundEcommerceGrowthRuntimeStore
from aos_api.aip_production_contract_store import (
    AipProductionContractStore,
    canonical_hash as production_contract_canonical_hash,
)
from aos_api.aip_agent_registry_store import AipAgentRegistryStore
from aos_api.aip_capability_registry import AipCapabilityRegistry
from aos_api.aip_binding_readiness_service import AipBindingReadinessService
from aos_api.aip_capability_binding_service import AipCapabilityBindingService
from aos_api.aip_skill_binding_readiness_service import AipSkillBindingReadinessService
from aos_api.aip_skill_registry import AipSkillRegistry
from aos_api.aip_budget_reservation_contracts import BudgetExactRef
from aos_api.aip_budget_reservation_store import (
    AipBudgetReservationStore,
    BudgetReservationError,
)
from aos_api.aip_agent_registry_contracts import (
    AgentInstanceStatus,
    CapabilityReadiness,
    TemplateLifecycle,
    VersionedAssetRef,
)
from aos_api.aip_model_runtime_contracts import (
    ModelModality,
    ModelRouteRevision,
    ModelRuntimeLifecycle,
    ProviderInstanceRevision,
    RegisteredModelRevision,
    RouteStrategy,
    RuntimePolicyRevision,
)
from aos_api.aip_model_runtime_store import (
    AipModelRuntimeStore,
    canonical_hash as model_runtime_canonical_hash,
    evaluation_candidate_ref,
)
from aos_api.aip_model_capacity_authority import (
    CapacityPoolRevisionCreate,
    canonical_hash as capacity_pool_canonical_hash,
)
from aos_api.aip_model_capacity_reservation import AipModelCapacityReservationGate
from aos_api.aip_production_contracts import (
    AssigneeKind,
    BriefLifecycle,
    ContractReadiness,
    Coverage,
    CreateBriefRequest,
    ExactArtifactRef,
    ExactRevisionRef,
    ReviewIssue,
    ReviewIssueStatus,
)
from aos_api.aip_eval_runner import AipEvalRunner, compute_eval_report_hash
from aos_api.aip_task_models import CreateTaskRequest, TaskTimeline
from aos_api.aip_contracts import ResourceRef, TaskRunStatus, TenantContext
from aos_api.ecommerce_analyst_authority_contracts import (
    AnalystExactRef,
    GrowthPlanRevision,
    GrowthPlanLifecycle,
)
from aos_api.ecommerce_analyst_authority_store import canonical_hash as analyst_canonical_hash
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_business_investigation_review_command import (
    EcommerceBusinessInvestigationReviewCommandService,
    review_issue_exact_ref,
)
from aos_api.ecommerce_business_investigation_aip_composition import (
    PostgresAipProductionCompositionSource,
)
from aos_api.ecommerce_business_investigation_application import (
    CreateBusinessInvestigationCaseRequest,
    CreateBusinessInvestigationRunRequest,
    EcommerceBusinessInvestigationApplication,
)
from aos_api.ecommerce_business_investigation_case import BusinessInvestigationCaseStore
from aos_api.ecommerce_business_investigation_schedule import (
    BusinessInvestigationSchedulePolicyRevision,
    BusinessInvestigationScheduleStore,
    PutBusinessInvestigationSchedulePolicyRequest,
)
from aos_api.aip_budget_reservation_store import canonical_hash as budget_canonical_hash
from aos_api.automation_occurrence_store import AutomationOccurrenceStore, ScheduleBinding
from aos_api.ecommerce_business_investigation_case_selection import (
    BusinessInvestigationCaseSelectionResolver,
    CatalogCanonicalProfileSelectionSource,
    PostgresCanonicalShopSelectionSource,
)
from aos_api.ecommerce_investigation_description_store import (
    InvestigationDescriptionStore,
    deterministic_receipt_id,
)
from aos_api.source_readiness import PostgresSourceReadinessFactSource, SourceReadinessService
from aos_api.data_requirement_store import DataRequirementStore
from aos_api.data_fulfillment_store import DataFulfillmentStore, canonical_fulfillment_content_hash
from aos_api.data_requirement_contracts import DataFulfillmentReceiptRecord
from aos_api.ecommerce_business_investigation_data_command import (
    EcommerceBusinessInvestigationDataCommandService,
    RequestBusinessInvestigationMissingDataCommand,
)
from aos_api.ecommerce_business_investigation_run import (
    BusinessInvestigationRunStore,
    BusinessInvestigationTriggerKind,
)
from aos_api.aip_business_investigation_runtime import BusinessInvestigationRuntimeBinder
from aos_api.aip_business_investigation_compile_saga import (
    BusinessInvestigationCompilationReceipt,
    BusinessInvestigationCompilationReceiptStore,
)
from aos_api.aip_task_store import AipTaskStore
from aos_api.tenant_scope import TenantScope


class _TransactionBoundConnection:
    """Compatibility view for existing stores without exposing commit control."""

    __slots__ = ("_transaction",)

    def __init__(self, transaction: HostTransaction) -> None:
        self._transaction = transaction

    def execute(self, query: str, params: tuple[Any, ...] = ()) -> Any:
        return self._transaction.execute(query, params)

    def commit(self) -> None:
        # The surrounding LockedEcommerceGrowthHostPort owns the only commit.
        return None

    def rollback(self) -> None:
        raise RuntimeError("transaction-bound domain store cannot roll back the host transaction")


class TransactionBoundConnectFactory:
    """Yield one scope-checked host transaction to existing domain Stores."""

    __slots__ = ("_connection", "_scope")

    def __init__(self, transaction: HostTransaction, scope: TenantScope) -> None:
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
            raise TypeError("host transaction and tenant scope are required")
        self._connection = _TransactionBoundConnection(transaction)
        self._scope = scope

    @contextmanager
    def __call__(self, requested_scope: TenantScope | None = None):
        if requested_scope is not None and requested_scope != self._scope:
            raise PermissionError("domain Store requested a different tenant scope")
        yield self._connection


def _strict_case_command(command: Mapping[str, Any]) -> tuple[str, CreateBusinessInvestigationCaseRequest, InvestigationExactRef]:
    if type(command) is not dict or set(command) != {"idempotencyKey", "case", "taskBriefRef"}:
        raise ValueError("case command must contain exactly idempotencyKey, case and taskBriefRef")
    key = command["idempotencyKey"]
    if type(key) is not str or not 1 <= len(key.strip()) <= 200:
        raise ValueError("case command idempotencyKey is invalid")
    if type(command["case"]) is not dict or type(command["taskBriefRef"]) is not dict:
        raise ValueError("case command authorities must be strict objects")
    request = CreateBusinessInvestigationCaseRequest.model_validate(command["case"])
    brief_ref = InvestigationExactRef.model_validate(command["taskBriefRef"])
    if brief_ref.resource_type != "TaskBriefRevision":
        raise ValueError("taskBriefRef must reference TaskBriefRevision")
    return key.strip(), request, brief_ref


def _case_ref(authority) -> dict[str, Any]:
    return {
        "resourceType": "BusinessInvestigationCaseRevision",
        "resourceId": authority.case_id,
        "revision": authority.revision,
        "contentHash": authority.content_hash,
    }


def _schedule_ref(authority: BusinessInvestigationSchedulePolicyRevision) -> dict[str, Any]:
    return {
        "resourceType": "SchedulePolicyRevision",
        "resourceId": authority.schedule_policy_id,
        "revision": authority.revision,
        "contentHash": authority.content_hash,
    }


def _strict_schedule_put_command(
    command: Mapping[str, Any],
) -> tuple[str, str, int, int, PutBusinessInvestigationSchedulePolicyRequest, InvestigationExactRef]:
    required = {
        "idempotencyKey",
        "caseId",
        "expectedPolicyRevision",
        "expectedCaseVersion",
        "policy",
        "approvalRef",
    }
    if type(command) is not dict or set(command) != required:
        raise ValueError("schedule put command has an invalid envelope")
    key, case_id = command["idempotencyKey"], command["caseId"]
    policy_revision = command["expectedPolicyRevision"]
    case_version = command["expectedCaseVersion"]
    if type(key) is not str or not 1 <= len(key.strip()) <= 200:
        raise ValueError("schedule put idempotencyKey is invalid")
    if type(case_id) is not str or not 1 <= len(case_id.strip()) <= 200:
        raise ValueError("schedule put caseId is invalid")
    if type(policy_revision) is not int or policy_revision < 0:
        raise ValueError("expectedPolicyRevision must be a non-negative integer")
    if type(case_version) is not int or case_version <= 0:
        raise ValueError("expectedCaseVersion must be a positive integer")
    if type(command["policy"]) is not dict or type(command["approvalRef"]) is not dict:
        raise ValueError("schedule put authorities must be strict objects")
    policy = PutBusinessInvestigationSchedulePolicyRequest.model_validate(command["policy"])
    approval_ref = InvestigationExactRef.model_validate(command["approvalRef"])
    if approval_ref.resource_type != "ActionApprovalEvent":
        raise ValueError("approvalRef must reference ActionApprovalEvent")
    return key.strip(), case_id.strip(), policy_revision, case_version, policy, approval_ref


def _json_object(value: Any) -> dict[str, Any]:
    if type(value) is str:
        value = json.loads(value)
    if type(value) is not dict:
        raise ValueError("stored authority payload must be an object")
    return value


def _lock_schedule_approval(
    transaction: HostTransaction,
    scope: TenantScope,
    approval_ref: InvestigationExactRef,
    *,
    checked_at: datetime,
    case_id: str,
    policy_id: str,
    expected_policy_revision: int,
    expected_case_version: int,
) -> None:
    approval = transaction.execute(
        """SELECT approval_event_id,proposal_id,proposal_version,proposal_hash,decision,
                  actor_id,reason,expires_at,created_at,action_binding_hash
             FROM aip_action_approval_event
            WHERE org_id=%s AND project_id=%s AND approval_event_id=%s FOR SHARE""",
        (*scope.key, approval_ref.resource_id),
    ).fetchone()
    if (
        approval is None
        or int(approval["proposal_version"]) != approval_ref.revision
        or approval["decision"] != "approved"
        or (approval["expires_at"] is not None and approval["expires_at"] <= checked_at)
    ):
        raise ValueError("active exact schedule ActionApprovalEvent is required")
    if budget_canonical_hash(dict(approval), prefixed=True) != approval_ref.content_hash:
        raise ValueError("schedule ActionApprovalEvent hash drifted")
    proposal = transaction.execute(
        """SELECT proposal_id,action_type_id,payload,proposal_hash,status,action_binding_hash
             FROM aip_action_proposal
            WHERE org_id=%s AND project_id=%s AND proposal_id=%s FOR SHARE""",
        (*scope.key, approval["proposal_id"]),
    ).fetchone()
    payload = _json_object(proposal["payload"]) if proposal is not None else {}
    expected_binding = {
        "caseId": case_id,
        "schedulePolicyId": policy_id,
        "expectedPolicyRevision": expected_policy_revision,
        "expectedCaseVersion": expected_case_version,
    }
    if (
        proposal is None
        or proposal["action_type_id"] != "ecommerce_growth_schedule_put"
        or proposal["status"] != "approved"
        or proposal["proposal_hash"] != approval["proposal_hash"]
        or not proposal["action_binding_hash"]
        or proposal["action_binding_hash"] != approval["action_binding_hash"]
        or any(payload.get(key) != value for key, value in expected_binding.items())
    ):
        raise ValueError("schedule approval is not bound to this exact Case and Policy revision")


def _strict_utc_seconds(value: Any, field: str) -> datetime:
    if type(value) is not str:
        raise ValueError(f"{field} must be an RFC3339 UTC string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an RFC3339 UTC string") from exc
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0 or parsed.microsecond:
        raise ValueError(f"{field} must be UTC with second precision")
    return parsed.astimezone(UTC)


def _strict_schedule_trigger_command(
    command: Mapping[str, Any],
) -> tuple[str, InvestigationExactRef, datetime, str, datetime]:
    required = {"idempotencyKey", "schedulePolicyRef", "scheduledAt", "localSlot", "deadline"}
    if type(command) is not dict or set(command) != required:
        raise ValueError("schedule trigger command has an invalid envelope")
    key, local_slot = command["idempotencyKey"], command["localSlot"]
    if type(key) is not str or not 1 <= len(key.strip()) <= 200:
        raise ValueError("schedule trigger idempotencyKey is invalid")
    if type(local_slot) is not str or not 1 <= len(local_slot.strip()) <= 120:
        raise ValueError("schedule trigger localSlot is invalid")
    if type(command["schedulePolicyRef"]) is not dict:
        raise ValueError("schedulePolicyRef must be a strict object")
    policy_ref = InvestigationExactRef.model_validate(command["schedulePolicyRef"])
    if policy_ref.resource_type != "SchedulePolicyRevision":
        raise ValueError("schedulePolicyRef must reference SchedulePolicyRevision")
    scheduled_at = _strict_utc_seconds(command["scheduledAt"], "scheduledAt")
    deadline = _strict_utc_seconds(command["deadline"], "deadline")
    if deadline <= scheduled_at:
        raise ValueError("schedule trigger deadline must be later than scheduledAt")
    return key.strip(), policy_ref, scheduled_at, local_slot.strip(), deadline


def _occurrence_payload(transaction: HostTransaction, scope: TenantScope, occurrence_id: UUID) -> dict[str, Any]:
    row = transaction.execute(
        """SELECT occurrence_id,policy_id,policy_revision,policy_hash,operation_id,
                  installation_id,generation,execution_epoch,scheduled_at,local_slot,
                  trigger_source,source_event_id,status,deadline
             FROM automation_occurrence
            WHERE org_id=%s AND project_id=%s AND occurrence_id=%s""",
        (*scope.key, occurrence_id),
    ).fetchone()
    if row is None:
        raise ValueError("AutomationOccurrence authority is missing")
    return {
        "occurrenceId": str(row["occurrence_id"]),
        "policyId": row["policy_id"],
        "policyRevision": int(row["policy_revision"]),
        "policyHash": row["policy_hash"],
        "operationId": row["operation_id"],
        "installationId": str(row["installation_id"]),
        "generation": str(row["generation"]),
        "executionEpoch": int(row["execution_epoch"]),
        "scheduledAt": row["scheduled_at"].isoformat(),
        "localSlot": row["local_slot"],
        "triggerSource": row["trigger_source"],
        "sourceEventId": row["source_event_id"],
        "status": row["status"],
        "deadline": row["deadline"].isoformat(),
    }


def _occurrence_ref(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "resourceType": "AutomationOccurrence",
        "resourceId": str(payload["occurrenceId"]),
        "revision": 1,
        "contentHash": budget_canonical_hash(dict(payload), prefixed=True),
    }


class _AlreadyValidatedCaseSelection:
    def verify_case_refs(self, *_args, **_kwargs) -> None:
        return None


def _strict_describe_command(command: Mapping[str, Any]) -> tuple[str, str]:
    if type(command) is not dict or set(command) != {"idempotencyKey", "analysisType"}:
        raise ValueError("investigation describe command has an invalid envelope")
    key, analysis_type = command["idempotencyKey"], command["analysisType"]
    if type(key) is not str or key != key.strip() or not 1 <= len(key) <= 200:
        raise ValueError("investigation describe idempotencyKey is invalid")
    if type(analysis_type) is not str or analysis_type != analysis_type.strip() or not 1 <= len(analysis_type) <= 120:
        raise ValueError("investigation describe analysisType is invalid")
    return key.strip(), analysis_type.strip()


class InvestigationDescribeHostService:
    """Persist a business-readable snapshot of current investigation readiness."""

    executor_identity = "ecommerce-growth-investigation-describe-host"

    @staticmethod
    def _selection(transaction, scope, checked_at, analysis_type):
        factory = TransactionBoundConnectFactory(transaction, scope)
        readiness_service = SourceReadinessService(
            PostgresSourceReadinessFactSource(
                factory,
                clock=lambda: checked_at,
                manage_transaction=False,
            )
        )

        readiness = readiness_service.read(org_id=scope.org_id, project_id=scope.project_id)

        class FixedReadiness:
            def read(self, *, org_id, project_id):
                if (org_id, project_id) != scope.key:
                    raise PermissionError("description readiness requested a different tenant")
                return readiness

        resolver = BusinessInvestigationCaseSelectionResolver(
            readiness_service=FixedReadiness(),
            shop_source=PostgresCanonicalShopSelectionSource(factory),
            profile_source=CatalogCanonicalProfileSelectionSource(
                composition_source=PostgresAipProductionCompositionSource(factory)
            ),
        )
        return resolver.read(scope, analysis_type), readiness

    @staticmethod
    def _authority(scope, key, analysis_type, selection, readiness, checked_at):
        selection_payload = selection.model_dump(by_alias=True, mode="json")
        readiness_payload = readiness.model_dump(by_alias=True, mode="json")
        blockers = list(selection_payload["blockers"])
        business_blockers = []
        if "SOURCE_READINESS_NOT_READY" in blockers:
            business_blockers.append("经营数据来源尚未达到分析要求")
        if "CANONICAL_SHOP_SELECTION_UNAVAILABLE" in blockers:
            business_blockers.append("当前没有唯一可用的经营门店")
        if any(item.startswith("INVESTIGATION_") for item in blockers):
            business_blockers.append("当前经营分析范围尚未配置完整")
        if blockers and not business_blockers:
            business_blockers.append("当前经营分析条件尚未核验完整")
        return {
            "schemaVersion": "aos.ecommerce.investigation-description/v1",
            "receiptId": str(deterministic_receipt_id(scope, key)),
            "analysisType": analysis_type,
            "businessTitle": "经营实体生意探究准备说明",
            "businessSummary": (
                "渠道、经营实体与数据来源已核验，可创建经营分析任务"
                if selection.case_creatable
                else "已完成经营条件核验，请先处理列出的业务条件"
            ),
            "caseCreatable": selection.case_creatable,
            "runCreatable": selection.run_creatable,
            "businessBlockers": business_blockers,
            "selection": selection_payload,
            "sourceReadiness": readiness_payload,
            "checkedAt": checked_at.astimezone(UTC).isoformat(),
        }

    def revalidate(self, *, transaction, scope, dispatch, command) -> None:
        _strict_describe_command(command)
        if dispatch.operation_id != "ecommerce_growth_investigation_describe":
            raise ValueError("investigation describe dispatch operation drifted")

    def execute(self, *, transaction, scope, dispatch_ref, command, checked_at, occurred_at):
        key, analysis_type = _strict_describe_command(command)
        store = InvestigationDescriptionStore(transaction, scope)
        request_hash = budget_canonical_hash(dict(command), prefixed=True)
        existing = store.read(
            deterministic_receipt_id(scope, key), request_hash=request_hash
        )
        if existing is not None:
            return {
                "receiptRef": existing.receipt_ref,
                "authority": existing.authority,
                "replayed": existing.replayed,
            }
        selection, readiness = self._selection(transaction, scope, checked_at, analysis_type)
        authority = self._authority(
            scope, key, analysis_type, selection, readiness, checked_at
        )
        record = store.put(
            idempotency_key=key,
            request_hash=request_hash,
            authority=authority,
            created_at=occurred_at or checked_at,
        )
        return {
            "receiptRef": record.receipt_ref,
            "authority": record.authority,
            "replayed": record.replayed,
        }

    def verify_receipt(self, *, transaction, scope, dispatch, command, receipt):
        key, analysis_type = _strict_describe_command(command)
        ref = receipt.get("receiptRef")
        if type(ref) is not dict or ref.get("resourceType") != "InvestigationDescriptionReceipt":
            return {}
        try:
            receipt_id = UUID(str(ref.get("resourceId")))
        except (TypeError, ValueError):
            return {}
        if receipt_id != deterministic_receipt_id(scope, key):
            return {}
        record = InvestigationDescriptionStore(transaction, scope).read(
            receipt_id, request_hash=budget_canonical_hash(dict(command), prefixed=True)
        )
        if record is None or record.authority.get("analysisType") != analysis_type:
            return {}
        expected = {
            "receiptRef": record.receipt_ref,
            "authority": record.authority,
            "replayed": bool(receipt.get("replayed")),
        }
        return expected if dict(receipt) == expected else {}


_DATA_SPEC_KEYS = {
    "purposeCode", "requiredFacts", "timeWindow", "grain", "cutoffAt",
    "freshnessMaxAgeSeconds", "qualityThreshold", "markings", "minPopulation",
    "acceptableDegradation", "requestedOutputs", "budgetMinor", "expiresAt",
}
_DATA_REF_TYPES = {
    "caseRef": "BusinessInvestigationCaseRevision", "runRef": "BusinessInvestigationRun",
    "checkpointRef": "CheckpointRevision", "channelRef": "ChannelRevision",
    "entityRef": "BusinessEntityRevision",
}


def _strict_data_request(command):
    expected = _DATA_SPEC_KEYS | set(_DATA_REF_TYPES) | {"operation", "idempotencyKey", "expectedRunVersion"}
    if type(command) is not dict or set(command) != expected or command["operation"] != "data.requirement.request":
        raise ValueError("data requirement command has an invalid envelope")
    key, version = command["idempotencyKey"], command["expectedRunVersion"]
    if type(key) is not str or key != key.strip() or not 1 <= len(key) <= 200:
        raise ValueError("data requirement idempotencyKey is invalid")
    if type(version) is not int or version < 1:
        raise ValueError("data requirement expectedRunVersion is invalid")
    refs = {}
    for name, kind in _DATA_REF_TYPES.items():
        value = command[name]
        if (type(value) is not dict or not {"resourceType", "resourceId", "revision", "contentHash"} <= set(value)
                or set(value) - {"resourceType", "resourceId", "revision", "contentHash", "receiptId"}
                or type(value["revision"]) is not int):
            raise ValueError("data requirement needs exact references")
        ref = InvestigationExactRef.model_validate(value)
        if ref.resource_type != kind:
            raise ValueError("data requirement reference type drifted")
        refs[name] = ref
    request = RequestBusinessInvestigationMissingDataCommand.model_validate_json(
        json.dumps({name: command[name] for name in _DATA_SPEC_KEYS}, allow_nan=False), strict=True
    )
    return key, version, refs, request


def _strict_data_bind(command):
    expected = {
        "operation", "idempotencyKey", "requirementRef", "sourceReadinessRef",
        "artifactRefs", "factRefs", "cutoffAt", "qualityScore", "sourceSummaryHash",
    }
    if type(command) is not dict or set(command) != expected or command["operation"] != "data.fulfillment.bind":
        raise ValueError("data fulfillment command has an invalid envelope")
    key = command["idempotencyKey"]
    if type(key) is not str or key != key.strip() or not 1 <= len(key) <= 200:
        raise ValueError("data fulfillment idempotencyKey is invalid")
    requirement = command["requirementRef"]
    readiness = command["sourceReadinessRef"]
    artifacts = command["artifactRefs"]
    facts = command["factRefs"]
    cutoff = command["cutoffAt"]
    quality = command["qualityScore"]
    summary = command["sourceSummaryHash"]
    if type(cutoff) is not str or not cutoff.strip():
        raise ValueError("data fulfillment cutoffAt is invalid")
    if type(quality) not in {int, float} or not math.isfinite(float(quality)) or not 0 < float(quality) <= 1:
        raise ValueError("data fulfillment qualityScore is invalid")
    if type(summary) is not str or not re.fullmatch(r"sha256:[0-9a-f]{64}", summary):
        raise ValueError("data fulfillment sourceSummaryHash is invalid")
    if type(artifacts) is not list or not artifacts or type(facts) is not list or not facts:
        raise ValueError("data fulfillment requires exact artifacts and facts")
    requirement_ref = InvestigationExactRef.model_validate(requirement)
    readiness_ref = InvestigationExactRef.model_validate(readiness)
    if requirement_ref.resource_type != "DataRequirementRevision":
        raise ValueError("data fulfillment requirement type drifted")
    if readiness_ref.resource_type != "SourceReadinessEnvelope" or readiness_ref.receipt_id is None:
        raise ValueError("data fulfillment source readiness drifted")
    artifact_refs = tuple(InvestigationExactRef.model_validate(item) for item in artifacts)
    fact_refs = tuple(InvestigationExactRef.model_validate(item) for item in facts)
    if any(item.resource_type != "FactRevision" for item in fact_refs):
        raise ValueError("data fulfillment fact type drifted")
    return key, requirement_ref, readiness_ref, artifact_refs, fact_refs, cutoff


class DataRequirementRequestHostService:
    """Request-only slice; registered DataFulfill awaits observation/bind wiring."""

    executor_identity = "ecommerce-growth-data-host"

    @staticmethod
    def _original_response(data, runs, scope, command):
        key, version, refs, request = _strict_data_request(command)
        original = data.find_command_receipt(scope, "request", key)
        if original is None:
            return None
        authority = original.authority
        serialized = authority.model_dump(by_alias=True, mode="json")
        requested = request.model_dump(by_alias=True, mode="json")
        if (authority.case_ref != refs["caseRef"] or authority.run_ref != refs["runRef"]
                or authority.checkpoint_ref != refs["checkpointRef"]
                or authority.channel_ref != refs["channelRef"] or authority.entity_ref != refs["entityRef"]
                or any(serialized[name] != requested[name] for name in _DATA_SPEC_KEYS)):
            raise ValueError("original data requirement command drifted")
        transition = runs.read_data_request_receipt(
            scope, refs["runRef"].resource_id, original.result.exact_ref,
            expected_version=version, idempotency_key=key,
        )
        if transition is None:
            return None
        return {"requirementRef": original.result.exact_ref.model_dump(by_alias=True, mode="json", exclude_none=True),
                "authority": serialized, "replayed": True}

    @staticmethod
    def _components(transaction, scope):
        factory = TransactionBoundConnectFactory(transaction, scope)
        cases = BusinessInvestigationCaseStore(factory)
        runs = BusinessInvestigationRunStore(factory)
        receipts = BusinessInvestigationCompilationReceiptStore(factory)
        binder = BusinessInvestigationRuntimeBinder(AipTaskStore(factory))
        data = DataRequirementStore(factory)
        service = EcommerceBusinessInvestigationDataCommandService(
            case_store=cases, run_store=runs, receipt_store=receipts,
            runtime_binder=binder, data_store=data,
        )
        return cases, runs, receipts, binder, data, service

    def revalidate(self, *, transaction, scope, dispatch, command):
        key, version, refs, request = _strict_data_request(command)
        if dispatch.operation_id != "ecommerce_growth_data_fulfill":
            raise ValueError("data requirement dispatch operation drifted")
        cases, runs, receipts, binder, data, _service = self._components(transaction, scope)
        if self._original_response(data, runs, scope, command) is not None:
            return
        run = runs.get(scope, refs["runRef"].resource_id)
        case = cases.get(scope, refs["caseRef"].resource_id)
        if (run.authority.case_ref != refs["caseRef"]
                or _case_ref(case) != refs["caseRef"].model_dump(by_alias=True, mode="json", exclude_none=True)
                or case.channel_ref != refs["channelRef"]
                or case.business_entity_ref != refs["entityRef"]
                or run.authority.version != refs["runRef"].revision
                or run.authority.content_hash != refs["runRef"].content_hash):
            raise ValueError("data requirement Case or Run lineage drifted")
        if data.find_command_receipt(scope, "request", key) is None and run.state.version != version:
            raise ValueError("data requirement Run version drifted")
        compilation = receipts.get_for_run(scope, refs["runRef"])
        runtime = binder.bind_receipt(scope, compilation, run)
        checkpoint = runtime.checkpoint_ref
        if (checkpoint is None or checkpoint.resource_id != refs["checkpointRef"].resource_id
                or checkpoint.sequence != refs["checkpointRef"].revision
                or "sha256:" + checkpoint.state_hash != refs["checkpointRef"].content_hash):
            raise ValueError("data requirement Checkpoint lineage drifted")

    def execute(self, *, transaction, scope, dispatch_ref, command, checked_at, occurred_at):
        key, version, refs, request = _strict_data_request(command)
        _cases, runs, _receipts, _binder, data, service = self._components(transaction, scope)
        original = self._original_response(data, runs, scope, command)
        if original is not None:
            return original
        result = service.request_missing_data(
            scope, refs["runRef"].resource_id, request, expected_version=version,
            idempotency_key=key, actor=self.executor_identity, occurred_at=occurred_at or checked_at,
        )
        authority = data.get_exact(scope, result.requirement_ref)
        return {"requirementRef": result.requirement_ref.model_dump(by_alias=True, mode="json", exclude_none=True),
                "authority": authority.model_dump(by_alias=True, mode="json"),
                "replayed": result.data_replayed}

    def verify_receipt(self, *, transaction, scope, dispatch, command, receipt):
        _cases, runs, _receipts, _binder, data, _service = self._components(transaction, scope)
        expected = self._original_response(data, runs, scope, command)
        if expected is None:
            return {}
        expected["replayed"] = bool(receipt.get("replayed"))
        return expected if dict(receipt) == expected else {}


class DataFulfillHostService:
    """Request plus fulfillment bind; client qualityScore never becomes Receipt authority."""

    executor_identity = DataRequirementRequestHostService.executor_identity

    def __init__(self) -> None:
        self._request = DataRequirementRequestHostService()

    @staticmethod
    def _bind_components(transaction, scope):
        factory = TransactionBoundConnectFactory(transaction, scope)
        return DataRequirementStore(factory), DataFulfillmentStore(factory)

    def revalidate(self, *, transaction, scope, dispatch, command):
        if type(command) is dict and command.get("operation") == "data.requirement.request":
            return self._request.revalidate(
                transaction=transaction, scope=scope, dispatch=dispatch, command=command
            )
        key, requirement_ref, _readiness, _artifacts, _facts, cutoff = _strict_data_bind(command)
        if dispatch.operation_id != "ecommerce_growth_data_fulfill":
            raise ValueError("data fulfillment dispatch operation drifted")
        data, _store = self._bind_components(transaction, scope)
        requirement = data.get_exact(scope, requirement_ref)
        if requirement.cutoff_at.astimezone(UTC).isoformat() != cutoff:
            raise ValueError("fulfillment cutoff drifted from requirement")
        if not key:
            raise ValueError("data fulfillment idempotencyKey is invalid")

    def execute(self, *, transaction, scope, dispatch_ref, command, checked_at, occurred_at):
        if type(command) is dict and command.get("operation") == "data.requirement.request":
            return self._request.execute(
                transaction=transaction,
                scope=scope,
                dispatch_ref=dispatch_ref,
                command=command,
                checked_at=checked_at,
                occurred_at=occurred_at,
            )
        key, requirement_ref, readiness_ref, artifacts, _facts, cutoff = _strict_data_bind(command)
        data, store = self._bind_components(transaction, scope)
        requirement = data.get_exact(scope, requirement_ref)
        if requirement.cutoff_at.astimezone(UTC).isoformat() != cutoff:
            raise ValueError("fulfillment cutoff drifted from requirement")
        fulfilled_at = occurred_at or checked_at
        record = DataFulfillmentReceiptRecord.model_validate(
            {
                "schemaVersion": "aos.data-fulfillment-authority-receipt/v1",
                "tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
                "fulfillmentId": key,
                "receiptId": key,
                "requirementRef": requirement_ref.model_dump(by_alias=True, exclude_none=True),
                "status": "fulfilled",
                "artifactRefs": [item.model_dump(by_alias=True, exclude_none=True) for item in artifacts],
                "sourceReadinessRef": readiness_ref.model_dump(by_alias=True, exclude_none=True),
                "cutoffAt": requirement.cutoff_at,
                "fulfilledAt": fulfilled_at,
                "contentHash": "sha256:" + "0" * 64,
                "createdBy": self.executor_identity,
                "blockers": [],
            }
        )
        record = record.model_copy(update={"content_hash": canonical_fulfillment_content_hash(record)})
        result = store.bind(scope, self.executor_identity, key, record)
        saved = store.read_exact(
            scope,
            InvestigationExactRef(
                resource_type="DataFulfillmentReceipt",
                resource_id=result.receipt_id,
                revision=1,
                content_hash=result.etag,
                receipt_id=result.receipt_id,
            ),
        )
        if saved is None:
            return {}
        return {
            "fulfillmentRef": {
                "resourceType": "DataFulfillmentReceipt",
                "resourceId": saved.receipt_id,
                "revision": 1,
                "contentHash": saved.content_hash,
                "receiptId": saved.receipt_id,
            }
        }

    def verify_receipt(self, *, transaction, scope, dispatch, command, receipt):
        if type(command) is dict and command.get("operation") == "data.requirement.request":
            return self._request.verify_receipt(
                transaction=transaction,
                scope=scope,
                dispatch=dispatch,
                command=command,
                receipt=receipt,
            )
        _key, _requirement_ref, _readiness, _artifacts, _facts, _cutoff = _strict_data_bind(command)
        ref = receipt.get("fulfillmentRef") if type(receipt) is dict else None
        if type(ref) is not dict:
            return {}
        _data, store = self._bind_components(transaction, scope)
        saved = store.read_exact(scope, InvestigationExactRef.model_validate(ref))
        if saved is None:
            return {}
        expected = {
            "fulfillmentRef": {
                "resourceType": "DataFulfillmentReceipt",
                "resourceId": saved.receipt_id,
                "revision": 1,
                "contentHash": saved.content_hash,
                "receiptId": saved.receipt_id,
            }
        }
        return expected if dict(receipt) == expected else {}


_ANALYSIS_START_FIELDS = frozenset(
    {
        "operation",
        "occurrenceRef",
        "caseRef",
        "profileRef",
        "cutoffAt",
        "idempotencyKey",
        "priorReceiptRef",
        "requirementRef",
        "fulfillmentRef",
        "checkpointRef",
        "requestHash",
    }
)
_ANALYSIS_START_PRIOR = (
    "priorReceiptRef",
    "requirementRef",
    "fulfillmentRef",
    "checkpointRef",
)
ANALYSIS_RECEIPT_NAMESPACE = UUID("a31a1c70-7d4e-4b2a-9c18-6e5f4d3c2b1a")


def _analysis_command_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _analysis_plan_ref(plan_ref) -> dict[str, Any]:
    payload = plan_ref.model_dump(by_alias=True, mode="json", exclude_none=True)
    content_hash = payload.get("contentHash")
    if type(content_hash) is str and not content_hash.startswith("sha256:"):
        payload["contentHash"] = "sha256:" + content_hash
    return payload


def _strict_analysis_start_command(command: Mapping[str, Any]) -> tuple[str, InvestigationExactRef, InvestigationExactRef, InvestigationExactRef]:
    if type(command) is not dict:
        raise ValueError("analysis command must be a strict mapping")
    operation = command.get("operation")
    if operation != "runtime.analysis.start":
        raise ValueError("analysis runtime mode is not wired")
    if set(command) != _ANALYSIS_START_FIELDS:
        raise ValueError("analysis start command has an invalid envelope")
    key = command["idempotencyKey"]
    request_hash = command["requestHash"]
    if type(key) is not str or key != key.strip() or not 1 <= len(key) <= 200:
        raise ValueError("analysis idempotencyKey is invalid")
    if type(request_hash) is not str or not re.fullmatch(r"sha256:[0-9a-f]{64}", request_hash):
        raise ValueError("analysis requestHash is invalid")
    body = {name: command[name] for name in command if name != "requestHash"}
    if _analysis_command_hash(body) != request_hash:
        raise ValueError("analysis request hash drifted")
    if any(command[name] is not None for name in _ANALYSIS_START_PRIOR):
        raise ValueError("START cannot claim prior runtime authority")
    cutoff = command["cutoffAt"]
    if type(cutoff) is not str:
        raise ValueError("analysis cutoffAt must be an ISO datetime")
    parsed = datetime.fromisoformat(cutoff)
    if parsed.utcoffset() is None:
        raise ValueError("analysis cutoffAt must include timezone")
    occurrence_ref = InvestigationExactRef.model_validate(command["occurrenceRef"])
    case_ref = InvestigationExactRef.model_validate(command["caseRef"])
    profile_ref = InvestigationExactRef.model_validate(command["profileRef"])
    if occurrence_ref.resource_type != "AutomationOccurrence":
        raise ValueError("analysis occurrence type drifted")
    if case_ref.resource_type != "BusinessInvestigationCaseRevision":
        raise ValueError("analysis case type drifted")
    if profile_ref.resource_type != "InvestigationProfileRevision":
        raise ValueError("analysis profile type drifted")
    return key, occurrence_ref, case_ref, profile_ref


class _HostAnalysisReceiptStore:
    """Persist AnalysisRuntimeReceipt so verify_receipt can reread before the adapter journal."""

    def __init__(self, transaction: HostTransaction, scope: TenantScope) -> None:
        self._transaction = transaction
        self._scope = scope

    def read(self, key: str) -> dict[str, Any] | None:
        return BoundEcommerceGrowthRuntimeStore(self._transaction, self._scope).read(
            operation_id="ecommerce_growth_analysis_advance",
            idempotency_key=key,
        )

    def put(
        self,
        key: str,
        payload: Mapping[str, Any],
        *,
        dispatch_ref=None,
        checked_at=None,
    ) -> dict[str, Any]:
        existing = self.read(key)
        body = dict(payload)
        if existing is not None:
            if existing != body:
                raise ValueError("analysis runtime Receipt idempotency content drift")
            return existing
        if dispatch_ref is None or checked_at is None:
            raise ValueError("analysis runtime Receipt persistence requires dispatch authority")
        row = self._transaction.execute(
            """SELECT revision FROM extension_runtime_binding
                WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s""",
            (
                *self._scope.key,
                UUID(str(dispatch_ref.installation_id)),
                UUID(str(dispatch_ref.generation)),
            ),
        ).fetchone()
        if row is None:
            raise ValueError("analysis runtime binding is missing")
        snapshot = EcommerceGrowthDispatchSnapshot(
            operation_id=dispatch_ref.operation_id,
            dispatch_revision=int(dispatch_ref.dispatch_revision),
            installation_id=UUID(str(dispatch_ref.installation_id)),
            generation=UUID(str(dispatch_ref.generation)),
            execution_epoch=int(dispatch_ref.execution_epoch),
            cutover_group_id=UUID(str(dispatch_ref.cutover_group_id)),
            cutover_group_revision=int(dispatch_ref.cutover_group_revision),
            runtime_revision=int(row["revision"]),
            checked_at=checked_at,
        )
        record = BoundEcommerceGrowthRuntimeStore(self._transaction, self._scope).put(
            operation_id="ecommerce_growth_analysis_advance",
            idempotency_key=key,
            request_hash=str(body["requestHash"]),
            dispatch=snapshot,
            response=body,
            target_receipt_ref=body["receiptRef"],
            actor="ecommerce-growth-analysis-host",
            occurred_at=checked_at,
        )
        return record.response


class AnalysisAdvanceHostService:
    """START-only recoverable analysis host; resume/reconcile remain fail-closed."""

    executor_identity = "ecommerce-growth-analysis-host"

    @staticmethod
    def _components(transaction, scope):
        factory = TransactionBoundConnectFactory(transaction, scope)
        return (
            lambda occurrence_id: _occurrence_payload(transaction, scope, occurrence_id),
            BusinessInvestigationCaseStore(factory),
            _HostAnalysisReceiptStore(transaction, scope),
        )

    @staticmethod
    def _occurrence_content_hash(payload: Mapping[str, Any]) -> str:
        return budget_canonical_hash(dict(payload), prefixed=True)

    def _start_lineage(self, *, transaction, scope, command, occurred_at):
        factory = TransactionBoundConnectFactory(transaction, scope)
        cases = BusinessInvestigationCaseStore(factory)
        runs = BusinessInvestigationRunStore(factory)
        receipts = BusinessInvestigationCompilationReceiptStore(factory)
        binder = BusinessInvestigationRuntimeBinder(AipTaskStore(factory))
        case = cases.get(scope, command["caseRef"]["resourceId"])
        run_id = "analysis-" + hashlib.sha256(
            "\x1f".join((*scope.key, command["idempotencyKey"])).encode()
        ).hexdigest()[:32]
        result = EcommerceBusinessInvestigationApplication(
            case_store=cases,
            run_store=runs,
            case_selection_resolver=_AlreadyValidatedCaseSelection(),
        ).create_run(
            scope,
            case.case_id,
            CreateBusinessInvestigationRunRequest(
                run_id=run_id,
                case_ref=InvestigationExactRef.model_validate(command["caseRef"]),
                analysis_type=case.analysis_type,
                trigger_kind=BusinessInvestigationTriggerKind.RECOVERY,
                trigger_key=command["idempotencyKey"],
            ),
            idempotency_key=command["idempotencyKey"],
            actor=self.executor_identity,
            occurred_at=occurred_at,
        )
        run = result.run
        run_ref = InvestigationExactRef(
            resource_type="BusinessInvestigationRun",
            resource_id=run.authority.run_id,
            revision=run.authority.version,
            content_hash=run.authority.content_hash,
        )
        compilation = receipts.get_for_run(scope, run_ref)
        runtime = binder.bind_receipt(scope, compilation, run)
        binding_hash = runtime.binding_hash
        if not binding_hash.startswith("sha256:"):
            binding_hash = "sha256:" + binding_hash
        return {
            "runRef": run_ref.model_dump(by_alias=True, mode="json", exclude_none=True),
            "compilationRef": compilation.exact_ref.model_dump(
                by_alias=True, mode="json", exclude_none=True
            ),
            "planRef": _analysis_plan_ref(compilation.plan_ref),
            "taskRunRef": {
                "resourceType": "TaskRun",
                "resourceId": runtime.task_run_ref.resource_id,
                "revision": runtime.task_run_ref.version,
                "contentHash": binding_hash,
            },
        }

    def _preparing_receipt(self, command, lineage, scope, key):
        body = {
            "requestHash": command["requestHash"],
            "occurrenceRef": command["occurrenceRef"],
            "caseRef": command["caseRef"],
            "profileRef": command["profileRef"],
            "cutoffAt": command["cutoffAt"],
            "runRef": lineage["runRef"],
            "compilationRef": lineage["compilationRef"],
            "planRef": lineage["planRef"],
            "taskRunRef": lineage["taskRunRef"],
            "phase": "PREPARING",
            "recoverableAction": "CONTINUE",
            "checkpointRef": None,
            "priorCheckpointRef": None,
            "requirementRef": None,
            "fulfillmentRef": None,
            "sourceReadinessRef": None,
            "mappingRef": None,
            "evidenceRefs": [],
            "observedAt": None,
            "targetReceiptRef": None,
            "completed": False,
        }
        receipt_id = str(uuid5(ANALYSIS_RECEIPT_NAMESPACE, "\x1f".join((*scope.key, key))))
        return {
            "receiptRef": {
                "resourceType": "AnalysisRuntimeReceipt",
                "resourceId": receipt_id,
                "revision": 1,
                "contentHash": _analysis_command_hash(body),
                "receiptId": receipt_id,
            },
            **body,
        }

    def revalidate(self, *, transaction, scope, dispatch, command):
        key, occurrence_ref, case_ref, profile_ref = _strict_analysis_start_command(command)
        if dispatch.operation_id != "ecommerce_growth_analysis_advance":
            raise ValueError("analysis dispatch operation drifted")
        occurrence_reader, cases, _receipts = self._components(transaction, scope)
        try:
            occurrence_id = UUID(str(occurrence_ref.resource_id))
        except (TypeError, ValueError) as exc:
            raise ValueError("analysis occurrence identity is invalid") from exc
        authority = occurrence_reader(occurrence_id)
        expected_occurrence = {
            "resourceType": "AutomationOccurrence",
            "resourceId": str(authority["occurrenceId"]),
            "revision": 1,
            "contentHash": self._occurrence_content_hash(authority),
        }
        if command["occurrenceRef"] != expected_occurrence:
            raise ValueError("analysis occurrence lineage drifted")
        case = cases.get(scope, case_ref.resource_id)
        if _case_ref(case) != command["caseRef"]:
            raise ValueError("analysis case lineage drifted")
        profile = case.investigation_profile_ref.model_dump(
            by_alias=True, mode="json", exclude_none=True
        )
        if profile != command["profileRef"] or profile_ref.resource_id != profile["resourceId"]:
            raise ValueError("analysis profile lineage drifted")
        if not key:
            raise ValueError("analysis idempotencyKey is invalid")

    def execute(self, *, transaction, scope, dispatch_ref, command, checked_at, occurred_at):
        key, _occurrence_ref, _case_ref_value, _profile_ref = _strict_analysis_start_command(command)
        _reader, _cases, receipts = self._components(transaction, scope)
        existing = receipts.read(key)
        if existing is not None:
            return existing
        lineage = self._start_lineage(
            transaction=transaction,
            scope=scope,
            command=command,
            occurred_at=occurred_at or checked_at,
        )
        payload = self._preparing_receipt(command, lineage, scope, key)
        return receipts.put(key, payload, dispatch_ref=dispatch_ref, checked_at=checked_at)

    def verify_receipt(self, *, transaction, scope, dispatch, command, receipt):
        key, _occurrence_ref, _case_ref_value, _profile_ref = _strict_analysis_start_command(command)
        _reader, _cases, receipts = self._components(transaction, scope)
        expected = receipts.read(key)
        if expected is None or type(receipt) is not dict:
            return {}
        return expected if dict(receipt) == expected else {}


_REVIEW_ACCEPT_FIELDS = frozenset(
    {
        "operation",
        "occurrenceRef",
        "caseRef",
        "runRef",
        "analysisReceiptRef",
        "currentPlanRef",
        "growthPlanRef",
        "reviewIssueRef",
        "evalReportRef",
        "artifactBindings",
        "decision",
        "returnStage",
        "targetModuleId",
        "sourceSlotId",
        "targetSlotId",
        "markings",
        "expiresAt",
        "taskSpec",
        "cutoffAt",
        "idempotencyKey",
        "requestHash",
    }
)
_REVIEW_ARTIFACT_FAMILIES = ("portrait", "diagnosis", "growth_plan", "evidence_summary")
_REVIEW_TASK_SPEC_FIELDS = frozenset(
    {
        "taskType",
        "briefType",
        "title",
        "objective",
        "channels",
        "audience",
        "timeWindow",
        "constraints",
        "growthPlanRef",
        "artifactRefs",
    }
)
_REVIEW_CJK = re.compile(r"[\u3400-\u9fff]")
_REVIEW_TECHNICAL_POLLUTION = re.compile(
    r"(?:(?:AR|W|R|N)\s*[-_]?\s*\d|技术方案|开发任务|波次|API|SQL|DDL|数据库迁移|代码|"
    r"(?:/[\w.-]+){2,}|(?:[\w.-]+/)+[\w.-]+\.(?:py|ts|tsx|js|sql|md|json|ya?ml)|"
    r"[A-Za-z]:\\+[^\\\s]+(?:\\+[^\\\s]+)+)",
    re.IGNORECASE,
)
REVIEW_RECEIPT_NAMESPACE = UUID("b42b2d81-8e5f-4c3b-ad29-7f6e5d4c3b2a")
REVIEW_HANDOFF_NAMESPACE = UUID("19ae5ab5-e974-46c0-8aa9-f70329bc7c03")
_REVIEW_SIDE_EFFECTS = {
    "externalEffectsAllowed": False,
    "providerInvocationCount": 0,
    "approvalCreatedCount": 0,
    "taskRunCreatedCount": 0,
    "externalPublicationCount": 0,
    "externalBusinessMutationCount": 0,
}


def _strict_review_accept_command(command: Mapping[str, Any]) -> tuple[str, InvestigationExactRef, InvestigationExactRef]:
    if type(command) is not dict:
        raise ValueError("review command must be a strict mapping")
    if command.get("operation") != "review_handoff.advance" or command.get("decision") != "ACCEPT":
        raise ValueError("review runtime mode is not wired")
    if set(command) != _REVIEW_ACCEPT_FIELDS:
        raise ValueError("review accept command has an invalid envelope")
    key = command["idempotencyKey"]
    request_hash = command["requestHash"]
    if type(key) is not str or key != key.strip() or not 1 <= len(key) <= 200:
        raise ValueError("review idempotencyKey is invalid")
    if type(request_hash) is not str or not re.fullmatch(r"sha256:[0-9a-f]{64}", request_hash):
        raise ValueError("review requestHash is invalid")
    body = {name: command[name] for name in command if name != "requestHash"}
    if _analysis_command_hash(body) != request_hash:
        raise ValueError("review request hash drifted")
    if (
        command["returnStage"] is not None
        or command["targetModuleId"] != "ecommerce.content-campaign"
        or command["sourceSlotId"] != "analyst.solution"
        or command["targetSlotId"] != "content.plan"
        or command["markings"] != ["internal"]
        or type(command["expiresAt"]) is not str
        or type(command["taskSpec"]) is not dict
    ):
        raise ValueError("ACCEPT requires an exact bounded content Handoff")
    cutoff = datetime.fromisoformat(command["cutoffAt"]) if type(command["cutoffAt"]) is str else None
    expires = datetime.fromisoformat(command["expiresAt"]) if type(command["expiresAt"]) is str else None
    if cutoff is None or expires is None or cutoff.utcoffset() is None or expires.utcoffset() is None:
        raise ValueError("review times must include timezone")
    if not cutoff < expires <= cutoff + timedelta(days=7):
        raise ValueError("ACCEPT Handoff expiry drifted")
    bindings = command["artifactBindings"]
    if type(bindings) is not list or tuple(item.get("family") for item in bindings if type(item) is dict) != _REVIEW_ARTIFACT_FAMILIES:
        raise ValueError("review requires four Artifacts in canonical family order")
    artifacts = []
    for item in bindings:
        artifact = InvestigationExactRef.model_validate(item["artifactRef"])
        if artifact.resource_type != "ArtifactRevision":
            raise ValueError("review artifact type drifted")
        artifacts.append(artifact)
    if len(set((item.resource_type, item.resource_id, item.revision, item.content_hash) for item in artifacts)) != 4:
        raise ValueError("review Artifact refs must be unique")
    task = command["taskSpec"]
    try:
        nested_growth_plan = InvestigationExactRef.model_validate(task["growthPlanRef"])
        outer_growth_plan = InvestigationExactRef.model_validate(command["growthPlanRef"])
        nested_artifacts = [
            InvestigationExactRef.model_validate(value) for value in task["artifactRefs"]
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("review content Task exact refs are invalid") from exc
    normalized_growth_plan = nested_growth_plan.model_dump(
        mode="json", by_alias=True, exclude_none=True
    )
    normalized_outer_growth_plan = outer_growth_plan.model_dump(
        mode="json", by_alias=True, exclude_none=True
    )
    normalized_artifacts = [
        value.model_dump(mode="json", by_alias=True, exclude_none=True)
        for value in nested_artifacts
    ]
    if (
        set(task) != _REVIEW_TASK_SPEC_FIELDS
        or task["taskType"] != "ecommerce.workshop.business_task"
        or task["briefType"] != "content_campaign"
        or nested_growth_plan.resource_type != "GrowthPlanRevision"
        or normalized_growth_plan != task["growthPlanRef"]
        or normalized_outer_growth_plan != command["growthPlanRef"]
        or normalized_growth_plan != normalized_outer_growth_plan
        or any(value.resource_type != "ArtifactRevision" for value in nested_artifacts)
        or normalized_artifacts != task["artifactRefs"]
        or normalized_artifacts != [item["artifactRef"] for item in bindings]
    ):
        raise ValueError("review content Task exact lineage drifted")
    text_limits = (
        (task["title"], 120),
        (task["objective"], 500),
        (task["audience"], 300),
        (task["timeWindow"], 200),
    )
    if any(type(value) is not str or not 1 <= len(value.strip()) <= limit for value, limit in text_limits):
        raise ValueError("review content Task text is invalid")
    channels = task["channels"]
    constraints = task["constraints"]
    values = (*channels, *constraints) if type(channels) is list and type(constraints) is list else ()
    if (
        type(channels) is not list
        or not 1 <= len(channels) <= 12
        or type(constraints) is not list
        or len(constraints) > 30
        or any(type(value) is not str or not 1 <= len(value.strip()) <= 200 for value in values)
        or len(values) != len(set(values))
    ):
        raise ValueError("review content Task business values are invalid")
    for value in (task["title"], task["objective"], *values, task["audience"], task["timeWindow"]):
        normalized = "".join(
            character
            for character in unicodedata.normalize("NFKC", value)
            if unicodedata.category(character) != "Cf"
        )
        if (
            normalized != value
            or value != value.strip()
            or not _REVIEW_CJK.search(normalized)
            or _REVIEW_TECHNICAL_POLLUTION.search(normalized)
        ):
            raise ValueError("review content Task must use Chinese business text")
    occurrence_ref = InvestigationExactRef.model_validate(command["occurrenceRef"])
    case_ref = InvestigationExactRef.model_validate(command["caseRef"])
    run_ref = InvestigationExactRef.model_validate(command["runRef"])
    analysis_ref = InvestigationExactRef.model_validate(command["analysisReceiptRef"])
    if occurrence_ref.resource_type != "AutomationOccurrence":
        raise ValueError("review occurrence type drifted")
    if case_ref.resource_type != "BusinessInvestigationCaseRevision":
        raise ValueError("review case type drifted")
    if run_ref.resource_type != "BusinessInvestigationRun":
        raise ValueError("review run type drifted")
    if analysis_ref.resource_type != "AnalysisRuntimeReceipt":
        raise ValueError("review analysis receipt type drifted")
    return key, occurrence_ref, case_ref


class _HostReviewReceiptStore:
    def __init__(self, transaction: HostTransaction, scope: TenantScope) -> None:
        self._inner = _HostAnalysisReceiptStore(transaction, scope)

    def read(self, key: str) -> dict[str, Any] | None:
        return BoundEcommerceGrowthRuntimeStore(self._inner._transaction, self._inner._scope).read(
            operation_id="ecommerce_growth_review_advance",
            idempotency_key=key,
        )

    def put(self, key: str, payload: Mapping[str, Any], *, dispatch_ref=None, checked_at=None) -> dict[str, Any]:
        existing = self.read(key)
        body = dict(payload)
        if existing is not None:
            if existing != body:
                raise ValueError("review Receipt idempotency content drift")
            return existing
        if dispatch_ref is None or checked_at is None:
            raise ValueError("review Receipt persistence requires dispatch authority")
        row = self._inner._transaction.execute(
            """SELECT revision FROM extension_runtime_binding
                WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s""",
            (
                *self._inner._scope.key,
                UUID(str(dispatch_ref.installation_id)),
                UUID(str(dispatch_ref.generation)),
            ),
        ).fetchone()
        if row is None:
            raise ValueError("review runtime binding is missing")
        snapshot = EcommerceGrowthDispatchSnapshot(
            operation_id=dispatch_ref.operation_id,
            dispatch_revision=int(dispatch_ref.dispatch_revision),
            installation_id=UUID(str(dispatch_ref.installation_id)),
            generation=UUID(str(dispatch_ref.generation)),
            execution_epoch=int(dispatch_ref.execution_epoch),
            cutover_group_id=UUID(str(dispatch_ref.cutover_group_id)),
            cutover_group_revision=int(dispatch_ref.cutover_group_revision),
            runtime_revision=int(row["revision"]),
            checked_at=checked_at,
        )
        record = BoundEcommerceGrowthRuntimeStore(self._inner._transaction, self._inner._scope).put(
            operation_id="ecommerce_growth_review_advance",
            idempotency_key=key,
            request_hash=str(body["requestHash"]),
            dispatch=snapshot,
            response=body,
            target_receipt_ref=body["receiptRef"],
            actor="ecommerce-growth-review-host",
            occurred_at=checked_at,
        )
        return record.response


class ReviewAdvanceHostService:
    """ACCEPT-only review Handoff host; RETURN remains fail-closed."""

    executor_identity = "ecommerce-growth-review-host"

    @staticmethod
    def _components(transaction, scope):
        factory = TransactionBoundConnectFactory(transaction, scope)
        return (
            lambda occurrence_id: _occurrence_payload(transaction, scope, occurrence_id),
            BusinessInvestigationCaseStore(factory),
            _HostReviewReceiptStore(transaction, scope),
        )

    @staticmethod
    def _occurrence_content_hash(payload: Mapping[str, Any]) -> str:
        return budget_canonical_hash(dict(payload), prefixed=True)

    @staticmethod
    def _revalidate_growth_plan(*, transaction, scope, command) -> None:
        supplied = InvestigationExactRef.model_validate(command["growthPlanRef"])
        if supplied.resource_type != "GrowthPlanRevision" or type(supplied.revision) is not int:
            raise ValueError("review GrowthPlan exact ref is invalid")
        owner_ref = AnalystExactRef(
            resource_type="GrowthPlanRevision",
            resource_id=supplied.resource_id,
            revision=supplied.revision,
            content_hash=supplied.content_hash.removeprefix("sha256:"),
        )
        locked = transaction.execute(
            """SELECT head.current_revision,revision.content_hash,revision.receipt_id,
                       revision.payload,revision.created_by
                FROM public.ecommerce_analyst_growth_plan_head head
                JOIN public.ecommerce_analyst_growth_plan_revision revision
                  ON revision.org_id=head.org_id AND revision.project_id=head.project_id
                 AND revision.plan_id=head.plan_id AND revision.revision=%s
                WHERE head.org_id=%s AND head.project_id=%s AND head.plan_id=%s
                FOR SHARE OF head""",
            (owner_ref.revision, *scope.key, owner_ref.resource_id),
        ).fetchone()
        if (
            locked is None
            or int(locked["current_revision"]) != owner_ref.revision
            or locked["content_hash"] != owner_ref.content_hash
        ):
            raise ValueError("review GrowthPlan is not the current exact revision")
        receipt = transaction.execute(
            """SELECT request_hash,result_ref,created_by
                FROM public.ecommerce_analyst_authority_receipt
                WHERE org_id=%s AND project_id=%s AND receipt_id=%s
                  AND operation='analyst.growth_plan_publish'""",
            (*scope.key, locked["receipt_id"]),
        ).fetchone()
        payload = locked["payload"]
        plan = GrowthPlanRevision.model_validate(payload)
        expected = {
            "resourceType": "GrowthPlanRevision",
            "resourceId": plan.plan_id,
            "revision": plan.revision,
            "contentHash": "sha256:" + plan.content_hash,
        }
        expected_owner_result = {
            "resourceType": "GrowthPlanRevision",
            "resourceId": plan.plan_id,
            "revision": plan.revision,
            "contentHash": plan.content_hash,
        }
        expected_request_hash = analyst_canonical_hash(
            {"expectedVersion": plan.revision - 1, "revision": payload}
        )
        if (
            expected != command["growthPlanRef"]
            or plan.lifecycle is not GrowthPlanLifecycle.APPROVED
            or plan.revision != owner_ref.revision
            or plan.version != owner_ref.revision
            or plan.tenant.org_id != scope.org_id
            or plan.tenant.project_id != scope.project_id
            or plan.content_hash != owner_ref.content_hash
            or plan.created_by != locked["created_by"]
            or receipt is None
            or receipt["request_hash"] != expected_request_hash
            or receipt["created_by"] != locked["created_by"]
            or receipt["result_ref"] != expected_owner_result
            or analyst_canonical_hash(receipt["result_ref"])
            != analyst_canonical_hash(expected_owner_result)
        ):
            raise ValueError("review GrowthPlan must be current and APPROVED")

    @staticmethod
    def _revalidate_issue_eval(*, transaction, scope, command) -> ReviewIssue:
        supplied_issue = InvestigationExactRef.model_validate(command["reviewIssueRef"])
        supplied_eval = InvestigationExactRef.model_validate(command["evalReportRef"])
        if (
            supplied_issue.resource_type != "ReviewIssueRevision"
            or supplied_eval.resource_type != "EvalReportRevision"
            or type(supplied_issue.revision) is not int
            or type(supplied_eval.revision) is not int
        ):
            raise ValueError("review Issue/Eval exact refs are invalid")
        row = transaction.execute(
            """SELECT * FROM public.aip_review_issue
                WHERE org_id=%s AND project_id=%s AND issue_id=%s
                FOR SHARE""",
            (*scope.key, supplied_issue.resource_id),
        ).fetchone()
        if row is None:
            raise ValueError("review Issue current authority is missing")
        issue = ReviewIssue(
            tenant={"orgId": scope.org_id, "projectId": scope.project_id},
            issue_id=row["issue_id"],
            rule_ref=ExactRevisionRef.model_validate(row["rule_ref"]),
            severity=row["severity"],
            artifact_ref=ExactArtifactRef(
                artifact_id=row["artifact_id"], content_hash=row["artifact_hash"]
            ),
            eval_report_ref=ExactRevisionRef(
                resource_type="EvalReportRevision",
                resource_id=row["eval_report_id"],
                revision=int(row["eval_report_revision"]),
                content_hash=row["eval_report_hash"],
            ),
            location=row["location"],
            evidence_refs=[
                ExactRevisionRef.model_validate(item) for item in row["evidence_refs"]
            ],
            suggested_fix=row["suggested_fix"],
            return_stage=row["return_stage"],
            status=row["status"],
            version=int(row["version"]),
            created_by=row["created_by"],
            created_at=row["created_at"],
            updated_by=row["updated_by"],
            updated_at=row["updated_at"],
        )
        issue_payload = issue.model_dump(mode="json", by_alias=True)
        raw_issue_payload = {
            **issue_payload,
            "ruleRef": row["rule_ref"],
            "location": row["location"],
            "evidenceRefs": row["evidence_refs"],
        }
        expected_issue = review_issue_exact_ref(issue).model_dump(mode="json", by_alias=True)
        if (
            budget_canonical_hash(raw_issue_payload)
            != budget_canonical_hash(issue_payload)
            or expected_issue["contentHash"]
            != "sha256:" + budget_canonical_hash(raw_issue_payload)
            or command["reviewIssueRef"] != expected_issue
            or issue.status is not ReviewIssueStatus.OPEN
            or issue.version != supplied_issue.revision
        ):
            raise ValueError("review Issue must be the current OPEN exact version")
        report_row = transaction.execute(
            """SELECT * FROM public.aip_eval_report_revision
                WHERE org_id=%s AND project_id=%s AND report_id=%s AND revision=%s""",
            (*scope.key, supplied_eval.resource_id, supplied_eval.revision),
        ).fetchone()
        if report_row is None:
            raise ValueError("review EvalReport authority is missing")
        report = AipEvalRunner._report_from_row(scope, report_row)
        report_payload = report.model_dump(
            mode="json", by_alias=True, exclude={"content_hash"}
        )
        raw_report_payload = {
            **report_payload,
            "suiteRef": report_row["suite_ref"],
            "evalContractRef": report_row["eval_contract_ref"],
            "subjectArtifactRef": report_row["subject_artifact_ref"],
            "stageAttemptRef": report_row["stage_attempt_ref"],
            "gatePolicyRef": report_row["gate_policy_ref"],
            "target": report_row["target_ref"],
            "dataset": report_row["dataset_ref"],
            "judge": report_row["judge_ref"],
            "results": report_row["results"],
        }
        expected_eval = {
            "resourceType": "EvalReportRevision",
            "resourceId": report.report_id,
            "revision": report.revision,
            "contentHash": "sha256:" + report.content_hash,
        }
        if (
            command["evalReportRef"] != expected_eval
            or budget_canonical_hash(raw_report_payload)
            != budget_canonical_hash(report_payload)
            or budget_canonical_hash(raw_report_payload) != report.content_hash
            or compute_eval_report_hash(report) != report.content_hash
        ):
            raise ValueError("review EvalReport exact authority drifted")
        try:
            EcommerceBusinessInvestigationReviewCommandService._validate_issue_report(
                issue, report
            )
        except RuntimeError as exc:
            raise ValueError("review Issue/Eval/Artifact lineage drifted") from exc
        return issue

    @staticmethod
    def _revalidate_artifacts(*, transaction, scope, command, issue: ReviewIssue) -> str:
        bindings = command["artifactBindings"]
        artifact_ids = [item["artifactRef"]["resourceId"] for item in bindings]
        rows = transaction.execute(
            """SELECT artifact_id,run_id,artifact_type,content_hash,family_revision
                FROM public.aip_artifact
                WHERE org_id=%s AND project_id=%s AND artifact_id=ANY(%s)""",
            (*scope.key, artifact_ids),
        ).fetchall()
        by_id = {row["artifact_id"]: row for row in rows}
        expected_refs = []
        run_ids = set()
        for binding in bindings:
            family = binding["family"]
            supplied = binding["artifactRef"]
            row = by_id.get(supplied["resourceId"])
            if (
                row is None
                or row["artifact_type"] != family
                or type(row["run_id"]) is not str
                or not row["run_id"]
                or row["run_id"] != row["run_id"].strip()
            ):
                raise ValueError("review Artifact family authority drifted")
            revision = (
                1 if row["family_revision"] is None else int(row["family_revision"])
            )
            expected = {
                "resourceType": "ArtifactRevision",
                "resourceId": row["artifact_id"],
                "revision": revision,
                "contentHash": "sha256:" + row["content_hash"],
            }
            if supplied != expected:
                raise ValueError("review Artifact exact authority drifted")
            expected_refs.append(expected)
            run_ids.add(row["run_id"])
        if len(rows) != 4 or len(run_ids) != 1:
            raise ValueError("review Artifacts must share one AIP TaskRun authority")
        if not any(
            ref["resourceId"] == issue.artifact_ref.artifact_id
            and ref["contentHash"] == "sha256:" + issue.artifact_ref.content_hash
            for ref in expected_refs
        ):
            raise ValueError("review Issue subject is outside the Artifact bindings")
        return next(iter(run_ids))

    @staticmethod
    def _revalidate_analysis_runtime(
        *, transaction, scope, command, artifact_task_run_id: str
    ) -> None:
        supplied = command["analysisReceiptRef"]
        receipt_rows = transaction.execute(
            """SELECT request_hash,response,target_receipt_ref
                FROM public.ecommerce_growth_runtime_command_receipt
                WHERE org_id=%s AND project_id=%s
                  AND operation_id='ecommerce_growth_analysis_advance'
                  AND target_receipt_ref->>'resourceId'=%s""",
            (*scope.key, supplied["resourceId"]),
        ).fetchall()
        if len(receipt_rows) != 1:
            raise ValueError("review AnalysisRuntimeReceipt authority is not unique")
        receipt_row = receipt_rows[0]
        response = receipt_row["response"]
        body = {key: value for key, value in response.items() if key != "receiptRef"}
        expected_analysis_ref = {
            "resourceType": "AnalysisRuntimeReceipt",
            "resourceId": supplied["resourceId"],
            "revision": 1,
            "contentHash": _analysis_command_hash(body),
            "receiptId": supplied["resourceId"],
        }
        if (
            supplied != expected_analysis_ref
            or response.get("receiptRef") != expected_analysis_ref
            or receipt_row["target_receipt_ref"] != expected_analysis_ref
            or response.get("requestHash") != receipt_row["request_hash"]
            or response.get("completed") is not False
            or response.get("runRef") != command["runRef"]
            or response.get("planRef") != command["currentPlanRef"]
            or type(response.get("compilationRef")) is not dict
            or type(response.get("taskRunRef")) is not dict
        ):
            raise ValueError("review AnalysisRuntimeReceipt exact lineage drifted")
        run_row = transaction.execute(
            """SELECT run.authority_data AS run_authority,
                       state.authority_data AS state_authority
                FROM public.ecommerce_investigation_run run
                JOIN public.ecommerce_investigation_run_state_head state
                  ON state.org_id=run.org_id AND state.project_id=run.project_id
                 AND state.run_id=run.run_id
                WHERE run.org_id=%s AND run.project_id=%s AND run.run_id=%s
                FOR SHARE OF state""",
            (*scope.key, command["runRef"]["resourceId"]),
        ).fetchone()
        if run_row is None:
            raise ValueError("review BusinessInvestigationRun authority is missing")
        from aos_api.ecommerce_business_investigation_run import (
            BusinessInvestigationRunRecord,
            BusinessInvestigationRunStateRevision,
        )

        domain_run = BusinessInvestigationRunRecord.model_validate(run_row["run_authority"])
        domain_state = BusinessInvestigationRunStateRevision.model_validate(
            run_row["state_authority"]
        )
        canonical_run = domain_run.model_dump(mode="json", by_alias=True)
        canonical_state = domain_state.model_dump(mode="json", by_alias=True)
        actual_run_ref = {
            "resourceType": "BusinessInvestigationRun",
            "resourceId": domain_run.run_id,
            "revision": domain_run.version,
            "contentHash": domain_run.content_hash,
        }
        if (
            command["runRef"] != actual_run_ref
            or budget_canonical_hash(run_row["run_authority"])
            != budget_canonical_hash(canonical_run)
            or domain_run.calculated_content_hash() != domain_run.content_hash
            or (domain_run.tenant.org_id, domain_run.tenant.project_id) != scope.key
            or domain_run.case_ref.model_dump(
                mode="json", by_alias=True, exclude_none=True
            )
            != command["caseRef"]
            or budget_canonical_hash(run_row["state_authority"])
            != budget_canonical_hash(canonical_state)
            or domain_state.calculated_content_hash() != domain_state.content_hash
            or domain_state.run_id != domain_run.run_id
            or (domain_state.tenant.org_id, domain_state.tenant.project_id) != scope.key
            or domain_state.control.value not in {"RUNNING", "PAUSED"}
        ):
            raise ValueError("review BusinessInvestigationRun exact authority drifted")
        compilation_ref = response["compilationRef"]
        compilation_row = transaction.execute(
            """SELECT receipt_data FROM public.aip_business_investigation_compile_receipt
                WHERE org_id=%s AND project_id=%s AND receipt_id=%s""",
            (*scope.key, compilation_ref["resourceId"]),
        ).fetchone()
        if compilation_row is None:
            raise ValueError("review compilation Receipt authority is missing")
        raw_compilation = compilation_row["receipt_data"]
        compilation = BusinessInvestigationCompilationReceipt.model_validate(raw_compilation)
        canonical_compilation = compilation.model_dump(mode="json", by_alias=True)
        if (
            budget_canonical_hash(raw_compilation) != budget_canonical_hash(canonical_compilation)
            or (compilation.tenant.org_id, compilation.tenant.project_id) != scope.key
            or compilation.exact_ref.model_dump(
                mode="json", by_alias=True, exclude_none=True
            )
            != compilation_ref
            or compilation.run_ref.model_dump(
                mode="json", by_alias=True, exclude_none=True
            )
            != command["runRef"]
            or _analysis_plan_ref(compilation.plan_ref) != command["currentPlanRef"]
        ):
            raise ValueError("review compilation Receipt exact lineage drifted")
        task_run_ref = response["taskRunRef"]
        historical_task_run_ref = InvestigationExactRef.model_validate(task_run_ref)
        if (
            historical_task_run_ref.model_dump(
                mode="json", by_alias=True, exclude_none=True
            )
            != task_run_ref
            or historical_task_run_ref.resource_type != "TaskRun"
            or type(historical_task_run_ref.revision) is not int
        ):
            raise ValueError("review historical TaskRun exact ref drifted")
        runtime_row = transaction.execute(
            """SELECT * FROM public.aip_task_run
                WHERE org_id=%s AND project_id=%s AND run_id=%s FOR SHARE""",
            (*scope.key, task_run_ref["resourceId"]),
        ).fetchone()
        if runtime_row is None:
            raise ValueError("review AIP runtime authority is missing")
        task_row = transaction.execute(
            """SELECT * FROM public.aip_task
                WHERE org_id=%s AND project_id=%s AND task_id=%s FOR SHARE""",
            (*scope.key, runtime_row["task_id"]),
        ).fetchone()
        plan_row = transaction.execute(
            """SELECT * FROM public.aip_plan_revision
                WHERE org_id=%s AND project_id=%s AND plan_revision_id=%s""",
            (*scope.key, runtime_row["plan_revision_id"]),
        ).fetchone()
        if task_row is None or plan_row is None:
            raise ValueError("review AIP Task/Plan authority is missing")
        checkpoints = transaction.execute(
            """SELECT * FROM public.aip_checkpoint
                WHERE org_id=%s AND project_id=%s AND run_id=%s ORDER BY sequence""",
            (*scope.key, task_run_ref["resourceId"]),
        ).fetchall()
        timeline = TaskTimeline(
            task=AipTaskStore._task(task_row),
            plan=AipTaskStore._plan(plan_row),
            run=AipTaskStore._run(runtime_row),
            checkpoints=[dict(row) for row in checkpoints],
        )
        binding = BusinessInvestigationRuntimeBinder._binding_from_lineage(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            case_ref=BusinessInvestigationRuntimeBinder._aip_ref(
                domain_run.case_ref, expected_type="BusinessInvestigationCaseRevision"
            ),
            run_ref=BusinessInvestigationRuntimeBinder._aip_ref(
                compilation.run_ref, expected_type="BusinessInvestigationRun"
            ),
            compilation_hash=compilation.compilation_hash,
            task_id=compilation.task_id,
            expected_plan_ref=compilation.plan_ref,
            task_run_id=task_run_ref["resourceId"],
            timeline=timeline,
        )
        if (
            historical_task_run_ref.resource_id != binding.task_run_ref.resource_id
            or historical_task_run_ref.revision > binding.task_run_ref.version
            or binding.task_run_status is not TaskRunStatus.SUCCEEDED
            or artifact_task_run_id != binding.task_run_ref.resource_id
        ):
            raise ValueError("review Analysis/Plan/TaskRun/Artifact lineage drifted")

    def _review_lineage(self, *, transaction, scope, command, occurred_at):
        if not isinstance(occurred_at, datetime) or occurred_at.utcoffset() is None:
            raise ValueError("review lineage time must include timezone")
        key = command["idempotencyKey"]
        task_spec = command["taskSpec"]
        handoff_body = {
            "operation": "review_handoff.accept",
            "occurrenceRef": command["occurrenceRef"],
            "caseRef": command["caseRef"],
            "runRef": command["runRef"],
            "analysisReceiptRef": command["analysisReceiptRef"],
            "currentPlanRef": command["currentPlanRef"],
            "growthPlanRef": command["growthPlanRef"],
            "reviewIssueRef": command["reviewIssueRef"],
            "evalReportRef": command["evalReportRef"],
            "artifactBindings": command["artifactBindings"],
            "targetModuleId": command["targetModuleId"],
            "sourceSlotId": command["sourceSlotId"],
            "targetSlotId": command["targetSlotId"],
            "markings": command["markings"],
            "expiresAt": command["expiresAt"],
        }
        handoff_id = str(
            uuid5(REVIEW_HANDOFF_NAMESPACE, "\x1f".join((*scope.key, key)))
        )
        handoff_ref = {
            "resourceType": "HandoffReceipt",
            "resourceId": handoff_id,
            "revision": 1,
            "contentHash": _analysis_command_hash(handoff_body),
            "receiptId": handoff_id,
        }
        factory = TransactionBoundConnectFactory(transaction, scope)
        task_goal = {
            "objective": task_spec["objective"],
            "sourceHandoffRef": handoff_ref,
            "growthPlanRef": command["growthPlanRef"],
            "artifactRefs": task_spec["artifactRefs"],
            "workshopAssignment": {
                "roleKey": "campaign_planner",
                "colleagueName": "活动策划师",
                "status": "requested",
            },
        }
        task_request = CreateTaskRequest(
            type=task_spec["taskType"],
            title=task_spec["title"],
            description=task_spec["objective"],
            goal=task_goal,
        )
        task = AipTaskStore(factory).create_task(
            scope,
            self.executor_identity,
            f"{key}:content-task",
            task_request,
        )
        task_payload = task_request.model_dump(mode="json", by_alias=True)
        expected_task_hash = _analysis_command_hash(task_payload).removeprefix("sha256:")
        task_row = transaction.execute(
            """SELECT request_hash,task_type,title,description,priority,goal,
                       selection_ref,policy_revision,version
                FROM public.aip_task
                WHERE org_id=%s AND project_id=%s AND task_id=%s
                  AND idempotency_key=%s""",
            (*scope.key, task.id, f"{key}:content-task"),
        ).fetchone()
        actual_task_payload = None if task_row is None else {
            "type": task_row["task_type"],
            "title": task_row["title"],
            "description": task_row["description"],
            "priority": int(task_row["priority"]),
            "goal": task_row["goal"],
            "selectionRef": task_row["selection_ref"],
            "policyRevision": task_row["policy_revision"],
        }
        if (
            task_row is None
            or actual_task_payload != task_payload
            or _analysis_command_hash(actual_task_payload).removeprefix("sha256:")
            != expected_task_hash
            or task_row["request_hash"] != expected_task_hash
            or int(task_row["version"]) != 1
        ):
            raise ValueError("review Task authority drifted")
        task_ref = {
            "resourceType": "Task",
            "resourceId": task.id,
            "revision": 1,
            "contentHash": "sha256:" + expected_task_hash,
        }
        brief_request = CreateBriefRequest(
            task_id=task.id,
            brief_type=task_spec["briefType"],
            schema_ref=ResourceRef(
                resource_type="ContentCampaignBriefSchema",
                resource_id="schema://aos/ecommerce/content-campaign-brief/v1",
                revision="1",
                authority="aos://ecommerce-workshop/content-campaign",
            ),
            spec={
                "sourceHandoffRef": handoff_ref,
                "taskRef": task_ref,
                "growthPlanRef": command["growthPlanRef"],
                "artifactRefs": task_spec["artifactRefs"],
                "objective": task_spec["objective"],
                "channels": task_spec["channels"],
                "audience": task_spec["audience"],
                "timeWindow": task_spec["timeWindow"],
                "constraints": task_spec["constraints"],
                "externalPublicationRequested": False,
            },
        )
        brief = AipProductionContractStore(factory).create_brief(
            scope,
            self.executor_identity,
            f"{key}:content-brief",
            brief_request,
        )
        brief_payload = brief_request.model_dump(mode="json", by_alias=True)
        expected_brief_request_hash = _analysis_command_hash(brief_payload).removeprefix(
            "sha256:"
        )
        expected_brief_content_hash = _analysis_command_hash(
            {
                "briefType": brief_payload["briefType"],
                "schemaRef": brief_payload["schemaRef"],
                "spec": brief_request.spec,
            }
        ).removeprefix("sha256:")
        brief_head = transaction.execute(
            """SELECT task_id,current_revision,version FROM public.aip_task_brief_head
                WHERE org_id=%s AND project_id=%s AND brief_id=%s""",
            (*scope.key, brief.brief_id),
        ).fetchone()
        brief_row = transaction.execute(
            """SELECT task_id,brief_type,schema_ref,spec,content_hash,lifecycle,created_by
                FROM public.aip_task_brief_revision
                WHERE org_id=%s AND project_id=%s AND brief_id=%s AND revision=1""",
            (*scope.key, brief.brief_id),
        ).fetchone()
        brief_receipt = transaction.execute(
            """SELECT request_hash,result_ref,created_by
                FROM public.aip_production_contract_receipt
                WHERE org_id=%s AND project_id=%s AND operation='task_brief.create'
                  AND idempotency_key=%s""",
            (*scope.key, f"{key}:content-brief"),
        ).fetchone()
        expected_brief_ref = {
            "resourceType": "TaskBriefRevision",
            "resourceId": brief.brief_id,
            "revision": 1,
            "contentHash": expected_brief_content_hash,
        }
        actual_brief_content_hash = None if brief_row is None else _analysis_command_hash(
            {
                "briefType": brief_row["brief_type"],
                "schemaRef": brief_row["schema_ref"],
                "spec": brief_row["spec"],
            }
        ).removeprefix("sha256:")
        actual_brief_result_hash = (
            None
            if brief_receipt is None
            else _analysis_command_hash(brief_receipt["result_ref"])
        )
        expected_brief_result_hash = _analysis_command_hash(expected_brief_ref)
        if (
            brief_head is None
            or brief_row is None
            or brief_receipt is None
            or brief_head["task_id"] != task.id
            or int(brief_head["current_revision"]) != 1
            or int(brief_head["version"]) != 1
            or brief_row["task_id"] != task.id
            or brief_row["brief_type"] != brief_payload["briefType"]
            or brief_row["schema_ref"] != brief_payload["schemaRef"]
            or brief_row["spec"] != brief_request.spec
            or actual_brief_content_hash != expected_brief_content_hash
            or brief_row["content_hash"] != expected_brief_content_hash
            or brief_row["lifecycle"] != "draft"
            or brief_row["created_by"] != self.executor_identity
            or brief_receipt["request_hash"] != expected_brief_request_hash
            or brief_receipt["result_ref"] != expected_brief_ref
            or actual_brief_result_hash != expected_brief_result_hash
            or brief_receipt["created_by"] != self.executor_identity
        ):
            raise ValueError("review TaskBrief authority drifted")
        return {
            "handoffRef": handoff_ref,
            "taskRef": task_ref,
            "briefRef": {
                "resourceType": "TaskBriefRevision",
                "resourceId": brief.brief_id,
                "revision": 1,
                "contentHash": "sha256:" + expected_brief_content_hash,
            },
        }

    def _accept_receipt(self, command, lineage, scope, key, decided_at):
        body = {
            "requestHash": command["requestHash"],
            "decision": "ACCEPT",
            "occurrenceRef": command["occurrenceRef"],
            "caseRef": command["caseRef"],
            "runRef": command["runRef"],
            "analysisReceiptRef": command["analysisReceiptRef"],
            "currentPlanRef": command["currentPlanRef"],
            "reviewIssueRef": command["reviewIssueRef"],
            "evalReportRef": command["evalReportRef"],
            "growthPlanRef": command["growthPlanRef"],
            "artifactBindings": command["artifactBindings"],
            "returnStage": None,
            "handoffRef": lineage["handoffRef"],
            "taskRef": lineage["taskRef"],
            "briefRef": lineage["briefRef"],
            "cutoffAt": command["cutoffAt"],
            "decidedAt": decided_at.astimezone(UTC).isoformat(),
            "replayed": False,
            "sideEffects": dict(_REVIEW_SIDE_EFFECTS),
        }
        receipt_id = str(uuid5(REVIEW_RECEIPT_NAMESPACE, "\x1f".join((*scope.key, key))))
        return {
            "receiptRef": {
                "resourceType": "ReviewDecisionReceipt",
                "resourceId": receipt_id,
                "revision": 1,
                "contentHash": _analysis_command_hash(body),
                "receiptId": receipt_id,
            },
            **body,
        }

    def revalidate(self, *, transaction, scope, dispatch, command):
        key, occurrence_ref, case_ref = _strict_review_accept_command(command)
        if dispatch.operation_id != "ecommerce_growth_review_advance":
            raise ValueError("review dispatch operation drifted")
        occurrence_reader, cases, _receipts = self._components(transaction, scope)
        try:
            occurrence_id = UUID(str(occurrence_ref.resource_id))
        except (TypeError, ValueError) as exc:
            raise ValueError("review occurrence identity is invalid") from exc
        authority = occurrence_reader(occurrence_id)
        expected_occurrence = {
            "resourceType": "AutomationOccurrence",
            "resourceId": str(authority["occurrenceId"]),
            "revision": 1,
            "contentHash": self._occurrence_content_hash(authority),
        }
        if command["occurrenceRef"] != expected_occurrence:
            raise ValueError("review occurrence lineage drifted")
        case = cases.get(scope, case_ref.resource_id)
        if _case_ref(case) != command["caseRef"]:
            raise ValueError("review case lineage drifted")
        self._revalidate_growth_plan(
            transaction=transaction,
            scope=scope,
            command=command,
        )
        issue = self._revalidate_issue_eval(
            transaction=transaction,
            scope=scope,
            command=command,
        )
        artifact_task_run_id = self._revalidate_artifacts(
            transaction=transaction,
            scope=scope,
            command=command,
            issue=issue,
        )
        self._revalidate_analysis_runtime(
            transaction=transaction,
            scope=scope,
            command=command,
            artifact_task_run_id=artifact_task_run_id,
        )
        if not key:
            raise ValueError("review idempotencyKey is invalid")

    def execute(self, *, transaction, scope, dispatch_ref, command, checked_at, occurred_at):
        key, _occurrence_ref, _case_ref_value = _strict_review_accept_command(command)
        _reader, _cases, receipts = self._components(transaction, scope)
        existing = receipts.read(key)
        if existing is not None:
            replay = dict(existing)
            replay["replayed"] = True
            return replay
        lineage = self._review_lineage(
            transaction=transaction,
            scope=scope,
            command=command,
            occurred_at=occurred_at or checked_at,
        )
        payload = self._accept_receipt(command, lineage, scope, key, occurred_at or checked_at)
        return receipts.put(key, payload, dispatch_ref=dispatch_ref, checked_at=checked_at)

    def verify_receipt(self, *, transaction, scope, dispatch, command, receipt):
        key, _occurrence_ref, _case_ref_value = _strict_review_accept_command(command)
        _reader, _cases, receipts = self._components(transaction, scope)
        expected = receipts.read(key)
        if expected is None or type(receipt) is not dict:
            return {}
        return expected if dict(receipt) == expected else {}


class CasePutHostService:
    """Current-authority Case write in the locked HostPort transaction."""

    executor_identity = "ecommerce-growth-case-host"

    @staticmethod
    def _factory(transaction: HostTransaction, scope: TenantScope) -> TransactionBoundConnectFactory:
        return TransactionBoundConnectFactory(transaction, scope)

    def revalidate(self, *, transaction, scope, dispatch, command) -> None:
        _key, request, brief_ref = _strict_case_command(command)
        factory = self._factory(transaction, scope)
        # Lock the mutable canonical Shop set before deriving its exact refs.
        transaction.execute(
            """SELECT external_id FROM ecom_object
                WHERE org_id=%s AND workspace_id=%s AND object_type='Shop'
                  AND deleted_at IS NULL AND canonical_status='active'
                ORDER BY platform,shop_or_marketplace_id,external_id FOR SHARE""",
            scope.key,
        ).fetchall()
        shop = PostgresCanonicalShopSelectionSource(factory).read(scope)
        profile = CatalogCanonicalProfileSelectionSource(
            composition_source=PostgresAipProductionCompositionSource(factory)
        ).read(scope, request.analysis_type.value)
        if shop is None or profile is None:
            raise ValueError("current Case selection authority is unavailable")
        expected = (
            shop.channel_ref,
            shop.business_entity_ref,
            shop.entity_channel_binding_ref,
            profile.investigation_profile_ref,
            profile.scope_ref,
        )
        actual = (
            request.channel_ref,
            request.business_entity_ref,
            request.entity_channel_binding_ref,
            request.investigation_profile_ref,
            request.scope_ref,
        )
        if actual != expected:
            raise ValueError("case command refs drifted from current canonical selection")
        brief_head = transaction.execute(
            """SELECT current_revision FROM aip_task_brief_head
                WHERE org_id=%s AND project_id=%s AND brief_id=%s FOR SHARE""",
            (*scope.key, brief_ref.resource_id),
        ).fetchone()
        if brief_head is None or int(brief_head["current_revision"]) != brief_ref.revision:
            raise ValueError("taskBriefRef is not the current revision")
        brief = AipProductionContractStore(factory).get_brief(
            scope, brief_ref.resource_id, brief_ref.revision, conn=transaction
        )
        brief_hash = brief.content_hash
        if not brief_hash.startswith("sha256:"):
            brief_hash = "sha256:" + brief_hash
        if brief_hash != brief_ref.content_hash or brief.lifecycle.value != "frozen":
            raise ValueError("taskBriefRef is not the current frozen authority")

    def execute(self, *, transaction, scope, dispatch_ref, command, checked_at, occurred_at):
        key, request, _brief_ref = _strict_case_command(command)
        factory = self._factory(transaction, scope)
        app = EcommerceBusinessInvestigationApplication(
            case_store=BusinessInvestigationCaseStore(factory),
            case_selection_resolver=_AlreadyValidatedCaseSelection(),
        )
        result = app.create_case(
            scope,
            request,
            idempotency_key=key,
            actor=self.executor_identity,
            occurred_at=occurred_at or checked_at,
        )
        return {
            "receiptRef": _case_ref(result.authority),
            "authority": result.authority.model_dump(by_alias=True, mode="json"),
            "replayed": result.replayed,
        }

    def verify_receipt(self, *, transaction, scope, dispatch, command, receipt):
        _key, request, _brief_ref = _strict_case_command(command)
        current = BusinessInvestigationCaseStore(self._factory(transaction, scope)).get(
            scope, request.case_id
        )
        expected = {
            "receiptRef": _case_ref(current),
            "authority": current.model_dump(by_alias=True, mode="json"),
            "replayed": bool(receipt.get("replayed")),
        }
        return expected if dict(receipt) == expected else {}


class SchedulePutHostService:
    """Current-authority SchedulePolicy write in the locked HostPort transaction."""

    executor_identity = "ecommerce-growth-schedule-host"

    @staticmethod
    def _factory(transaction: HostTransaction, scope: TenantScope) -> TransactionBoundConnectFactory:
        return TransactionBoundConnectFactory(transaction, scope)

    def revalidate(self, *, transaction, scope, dispatch, command) -> None:
        _key, case_id, expected_policy_revision, expected_case_version, policy, approval_ref = (
            _strict_schedule_put_command(command)
        )
        case_head = transaction.execute(
            """SELECT current_revision FROM ecommerce_investigation_case_head
                WHERE org_id=%s AND project_id=%s AND case_id=%s FOR SHARE""",
            (*scope.key, case_id),
        ).fetchone()
        if case_head is None or int(case_head["current_revision"]) != expected_case_version:
            raise ValueError("schedule Case authority is not current")
        case = BusinessInvestigationCaseStore(self._factory(transaction, scope)).get(scope, case_id)
        if (
            policy.case_ref.resource_type != "BusinessInvestigationCaseRevision"
            or policy.case_ref.resource_id != case_id
            or policy.case_ref.revision != expected_case_version
            or policy.case_ref.content_hash != case.content_hash
            or policy.analysis_type is not case.analysis_type
        ):
            raise ValueError("schedule policy does not bind the current exact Case")
        policy_head = transaction.execute(
            """SELECT current_revision FROM ecommerce_investigation_schedule_policy_head
                WHERE org_id=%s AND project_id=%s AND schedule_policy_id=%s FOR SHARE""",
            (*scope.key, policy.schedule_policy_id),
        ).fetchone()
        actual_policy_revision = 0 if policy_head is None else int(policy_head["current_revision"])
        if actual_policy_revision != expected_policy_revision:
            raise ValueError("schedule Policy authority is not current")
        if expected_policy_revision:
            current = BusinessInvestigationScheduleStore(self._factory(transaction, scope)).get(
                scope, policy.schedule_policy_id
            )
            if current.revision != expected_policy_revision:
                raise ValueError("schedule Policy revision drifted")
        _lock_schedule_approval(
            transaction,
            scope,
            approval_ref,
            checked_at=dispatch.checked_at,
            case_id=case_id,
            policy_id=policy.schedule_policy_id,
            expected_policy_revision=expected_policy_revision,
            expected_case_version=expected_case_version,
        )

    def execute(self, *, transaction, scope, dispatch_ref, command, checked_at, occurred_at):
        key, case_id, policy_revision, case_version, policy, approval_ref = (
            _strict_schedule_put_command(command)
        )
        factory = self._factory(transaction, scope)
        result = EcommerceBusinessInvestigationApplication(
            case_store=BusinessInvestigationCaseStore(factory),
            schedule_store=BusinessInvestigationScheduleStore(factory),
        ).put_schedule_policy(
            scope,
            case_id,
            policy,
            expected_policy_revision=policy_revision,
            expected_case_version=case_version,
            idempotency_key=key,
            actor=self.executor_identity,
            occurred_at=occurred_at or checked_at,
        )
        AutomationOccurrenceStore(factory).disable_policy_bindings(
            scope,
            result.authority.schedule_policy_id,
            keep_revision=result.authority.revision if result.authority.enabled else None,
        )
        return {
            "receiptRef": _schedule_ref(result.authority),
            "authority": result.authority.model_dump(by_alias=True, mode="json"),
            "caseAuthority": result.case_authority.model_dump(by_alias=True, mode="json"),
            "approvalRef": approval_ref.model_dump(by_alias=True, mode="json"),
            "replayed": result.replayed,
        }

    def verify_receipt(self, *, transaction, scope, dispatch, command, receipt):
        _key, case_id, _policy_revision, _case_version, policy, approval_ref = (
            _strict_schedule_put_command(command)
        )
        factory = self._factory(transaction, scope)
        current = BusinessInvestigationScheduleStore(factory).get(scope, policy.schedule_policy_id)
        current_case = BusinessInvestigationCaseStore(factory).get(scope, case_id)
        expected = {
            "receiptRef": _schedule_ref(current),
            "authority": current.model_dump(by_alias=True, mode="json"),
            "caseAuthority": current_case.model_dump(by_alias=True, mode="json"),
            "approvalRef": approval_ref.model_dump(by_alias=True, mode="json"),
            "replayed": bool(receipt.get("replayed")),
        }
        return expected if dict(receipt) == expected else {}


class ScheduleTriggerHostService:
    """Create one deterministic occurrence bound to the current runtime epoch."""

    executor_identity = "ecommerce-growth-occurrence-host"

    @staticmethod
    def _factory(transaction: HostTransaction, scope: TenantScope) -> TransactionBoundConnectFactory:
        return TransactionBoundConnectFactory(transaction, scope)

    def revalidate(self, *, transaction, scope, dispatch, command) -> None:
        _key, policy_ref, scheduled_at, local_slot, deadline = (
            _strict_schedule_trigger_command(command)
        )
        head = transaction.execute(
            """SELECT current_revision FROM ecommerce_investigation_schedule_policy_head
                WHERE org_id=%s AND project_id=%s AND schedule_policy_id=%s FOR SHARE""",
            (*scope.key, policy_ref.resource_id),
        ).fetchone()
        if head is None or int(head["current_revision"]) != policy_ref.revision:
            raise ValueError("schedulePolicyRef is not current")
        policy = BusinessInvestigationScheduleStore(self._factory(transaction, scope)).get(
            scope, policy_ref.resource_id
        )
        if _schedule_ref(policy) != policy_ref.model_dump(
            by_alias=True, mode="json", exclude_none=True
        ):
            raise ValueError("schedulePolicyRef exact authority drifted")
        if not policy.enabled or policy.cadence.value not in {"once", "weekly"}:
            raise ValueError("only an enabled once or weekly SchedulePolicy may trigger")
        local = scheduled_at.astimezone(ZoneInfo("Asia/Shanghai"))
        expected_local_slot = local.strftime("%Y-%m-%dT%H:%M%z")
        if local_slot != expected_local_slot:
            raise ValueError("localSlot does not match the Asia/Shanghai natural slot")
        if policy.cadence.value == "weekly" and (
            local.isoweekday() != policy.weekly_day
            or local.strftime("%H:%M") != policy.local_time
        ):
            raise ValueError("scheduledAt does not match the weekly Policy slot")
        if scheduled_at < policy.created_at.astimezone(UTC):
            raise ValueError("scheduledAt is before the Policy effective interval")
        checked_second = dispatch.checked_at.astimezone(UTC).replace(microsecond=0)
        if scheduled_at > checked_second:
            raise ValueError("scheduledAt is a future slot")
        if checked_second - scheduled_at > timedelta(hours=24):
            raise ValueError("scheduledAt is outside the bounded recovery window")
        if deadline != checked_second + timedelta(hours=24):
            raise ValueError("deadline does not match the bounded host recovery window")
        if (
            dispatch.operation_id != "ecommerce_growth_schedule_trigger"
            or dispatch.execution_epoch <= 0
        ):
            raise ValueError("schedule trigger runtime epoch is invalid")

    def execute(self, *, transaction, scope, dispatch_ref, command, checked_at, occurred_at):
        _key, policy_ref, scheduled_at, local_slot, deadline = _strict_schedule_trigger_command(
            command
        )
        factory = self._factory(transaction, scope)
        policy = BusinessInvestigationScheduleStore(factory).get(scope, policy_ref.resource_id)
        binding = ScheduleBinding(
            policy_id=policy.schedule_policy_id,
            policy_revision=policy.revision,
            policy_hash=policy.content_hash,
            operation_id="ecommerce_growth_schedule_trigger",
            installation_id=UUID(str(dispatch_ref.installation_id)),
            generation=UUID(str(dispatch_ref.generation)),
            execution_epoch=int(dispatch_ref.execution_epoch),
            cadence=policy.cadence.value,
            effective_from=policy.created_at,
            weekly_day=policy.weekly_day,
            local_time=policy.local_time,
            approved=True,
            enabled=True,
        )
        occurrences = AutomationOccurrenceStore(factory)
        occurrences.put_binding(scope, binding)
        write = occurrences.record_scheduled(
            scope,
            binding,
            scheduled_at=scheduled_at,
            local_slot=local_slot,
            deadline=deadline,
        )
        authority = _occurrence_payload(transaction, scope, write.occurrence_id)
        return {
            "occurrenceRef": _occurrence_ref(authority),
            "authority": authority,
            "status": authority["status"],
            "replayed": write.replayed,
        }

    def verify_receipt(self, *, transaction, scope, dispatch, command, receipt):
        _key, policy_ref, scheduled_at, local_slot, deadline = (
            _strict_schedule_trigger_command(command)
        )
        ref = receipt.get("occurrenceRef")
        if type(ref) is not dict:
            return {}
        try:
            occurrence_id = UUID(str(ref.get("resourceId")))
        except (TypeError, ValueError):
            return {}
        authority = _occurrence_payload(transaction, scope, occurrence_id)
        if (
            authority["policyId"] != policy_ref.resource_id
            or authority["policyRevision"] != policy_ref.revision
            or authority["policyHash"] != policy_ref.content_hash
            or authority["operationId"] != dispatch.operation_id
            or authority["installationId"] != str(dispatch.installation_id)
            or authority["generation"] != str(dispatch.generation)
            or authority["executionEpoch"] != dispatch.execution_epoch
            or authority["scheduledAt"] != scheduled_at.isoformat()
            or authority["localSlot"] != local_slot
            or authority["deadline"] != deadline.isoformat()
            or authority["triggerSource"] != "schedule"
            or authority["sourceEventId"] is not None
        ):
            return {}
        expected = {
            "occurrenceRef": _occurrence_ref(authority),
            "authority": authority,
            "status": authority["status"],
            "replayed": bool(receipt.get("replayed")),
        }
        return expected if dict(receipt) == expected else {}


class TrustedEcommerceGrowthDomainService(Protocol):
    executor_identity: str

    def revalidate(
        self,
        *,
        transaction: HostTransaction,
        scope: TenantScope,
        dispatch: EcommerceGrowthDispatchSnapshot,
        command: Mapping[str, Any],
    ) -> None: ...

    def execute(
        self,
        *,
        transaction: HostTransaction,
        scope: TenantScope,
        dispatch_ref: DispatchAuthorityRef,
        command: Mapping[str, Any],
        checked_at,
        occurred_at,
    ) -> Mapping[str, Any]: ...

    def verify_receipt(
        self,
        *,
        transaction: HostTransaction,
        scope: TenantScope,
        dispatch: EcommerceGrowthDispatchSnapshot,
        command: Mapping[str, Any],
        receipt: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class _AdapterSpec:
    operation_id: str
    authority_kinds: tuple[str, ...]
    receipt_keys: tuple[str, ...]


def _request_hash(command: Mapping[str, Any]) -> str:
    payload = json.dumps(command, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


class _ExplicitRuntimeAdapter:
    SPEC: _AdapterSpec

    def __init__(self, service: TrustedEcommerceGrowthDomainService) -> None:
        identity = getattr(service, "executor_identity", None)
        if type(identity) is not str or not 1 <= len(identity.strip()) <= 240:
            raise TypeError("trusted ecommerce domain service identity is required")
        if not all(callable(getattr(service, name, None)) for name in ("revalidate", "execute", "verify_receipt")):
            raise TypeError("trusted ecommerce domain service contract is incomplete")
        self._service = service

    def binding(self) -> EcommerceGrowthOperationBinding:
        return EcommerceGrowthOperationBinding(
            operation_id=self.SPEC.operation_id,
            authority_kinds=self.SPEC.authority_kinds,
            receipt_keys=self.SPEC.receipt_keys,
            revalidate=self._service.revalidate,
            execute=self._service.execute,
            verify_receipt=self._verify_and_journal,
        )

    def _verify_and_journal(
        self,
        *,
        transaction: HostTransaction,
        scope: TenantScope,
        dispatch: EcommerceGrowthDispatchSnapshot,
        command: Mapping[str, Any],
        receipt: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        persisted = self._service.verify_receipt(
            transaction=transaction,
            scope=scope,
            dispatch=dispatch,
            command=command,
            receipt=receipt,
        )
        if not isinstance(persisted, Mapping) or dict(persisted) != dict(receipt):
            return persisted
        targets = [
            receipt.get(key)
            for key in self.SPEC.receipt_keys
            if receipt.get(key) is not None
        ]
        if len(targets) != 1 or type(targets[0]) is not dict:
            return {}
        request_hash = _request_hash(command)
        idempotency_key = command.get("idempotencyKey")
        if type(idempotency_key) is not str or not idempotency_key.strip():
            idempotency_key = "read:" + request_hash.removeprefix("sha256:")
        record = BoundEcommerceGrowthRuntimeStore(transaction, scope).put(
            operation_id=self.SPEC.operation_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            dispatch=dispatch,
            response=dict(receipt),
            target_receipt_ref=targets[0],
            actor=self._service.executor_identity,
            occurred_at=dispatch.checked_at,
        )
        return record.response


_CONTENT_GENERATE_AUTHORITY_TYPES = {
    "handoff": "HandoffReceipt",
    "task": "Task",
    "brief": "TaskBriefRevision",
    "growth_plan": "GrowthPlanRevision",
    "agent_instance": "AgentInstanceRevision",
    "responsibility_plan": "ResponsibilityPlanRevision",
    "capability": "CapabilityRevision",
    "model_route": "ModelRouteRevision",
    "budget": "BudgetRevision",
    "pricing": "ModelPriceSnapshotRevision",
    "approval": "ActionApprovalEvent",
    "capacity_reservation": "CapacityReservation",
}
_CONTENT_GENERATE_FIELDS = frozenset(
    {
        "operation",
        "authorityRefs",
        "sourceArtifactRefs",
        "factSourceRefs",
        "currency",
        "upperBoundFen",
        "maxInputTokens",
        "maxOutputTokens",
        "idempotencyKey",
        "requestHash",
    }
)
_CONTENT_REVIEW_RECEIPT_FIELDS = frozenset(
    {
        "receiptRef",
        "requestHash",
        "decision",
        "occurrenceRef",
        "caseRef",
        "runRef",
        "analysisReceiptRef",
        "currentPlanRef",
        "reviewIssueRef",
        "evalReportRef",
        "growthPlanRef",
        "artifactBindings",
        "returnStage",
        "handoffRef",
        "taskRef",
        "briefRef",
        "cutoffAt",
        "decidedAt",
        "replayed",
        "sideEffects",
    }
)
_CONTENT_BRIEF_SPEC_FIELDS = frozenset(
    {
        "sourceHandoffRef",
        "taskRef",
        "growthPlanRef",
        "artifactRefs",
        "objective",
        "channels",
        "audience",
        "timeWindow",
        "constraints",
        "externalPublicationRequested",
    }
)


def _content_exact_ref(value: Any, expected_type: str) -> InvestigationExactRef:
    base_fields = {"resourceType", "resourceId", "revision", "contentHash"}
    if type(value) is not dict or set(value) not in {
        frozenset(base_fields),
        frozenset(base_fields | {"receiptId"}),
    }:
        raise ValueError("content generate exact ref fields drifted")
    ref = InvestigationExactRef.model_validate(value)
    if (
        ref.resource_type != expected_type
        or type(ref.revision) is not int
        or ref.model_dump(mode="json", by_alias=True, exclude_none=True) != value
    ):
        raise ValueError("content generate exact ref drifted")
    return ref


def _strict_content_generate_command(command: Mapping[str, Any]) -> dict[str, Any]:
    if type(command) is not dict or set(command) != _CONTENT_GENERATE_FIELDS:
        raise ValueError("content generate command envelope drifted")
    if command["operation"] != "content.generate":
        raise ValueError("content generate operation drifted")
    key = command["idempotencyKey"]
    request_hash = command["requestHash"]
    if (
        type(key) is not str
        or key != key.strip()
        or not 1 <= len(key) <= 200
        or type(request_hash) is not str
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", request_hash)
        or _analysis_command_hash(
            {name: value for name, value in command.items() if name != "requestHash"}
        )
        != request_hash
    ):
        raise ValueError("content generate command identity drifted")
    authorities = command["authorityRefs"]
    if type(authorities) is not dict or set(authorities) != set(
        _CONTENT_GENERATE_AUTHORITY_TYPES
    ):
        raise ValueError("content generate authority set drifted")
    parsed_authorities = {
        name: _content_exact_ref(authorities[name], kind)
        for name, kind in _CONTENT_GENERATE_AUTHORITY_TYPES.items()
    }
    source_values = command["sourceArtifactRefs"]
    fact_values = command["factSourceRefs"]
    if (
        type(source_values) is not list
        or len(source_values) != 4
        or type(fact_values) is not list
        or not 1 <= len(fact_values) <= 200
    ):
        raise ValueError("content generate source closure is invalid")
    source_refs = [_content_exact_ref(value, "ArtifactRevision") for value in source_values]
    fact_refs = []
    for value in fact_values:
        if type(value) is not dict or value.get("resourceType") not in {
            "EvidenceBundleRevision",
            "DatasetRevision",
            "DataFulfillmentReceipt",
        }:
            raise ValueError("content generate fact source type drifted")
        fact_refs.append(_content_exact_ref(value, value["resourceType"]))
    identities = lambda refs: {
        (ref.resource_type, ref.resource_id, ref.revision, ref.content_hash)
        for ref in refs
    }
    if len(identities(source_refs)) != 4 or len(identities(fact_refs)) != len(fact_refs):
        raise ValueError("content generate source refs must be unique")
    numeric = (
        (command["upperBoundFen"], 1, 100_000_000),
        (command["maxInputTokens"], 1, 1_000_000),
        (command["maxOutputTokens"], 1, 1_000_000),
    )
    if command["currency"] != "CNY" or any(
        type(value) is not int or not lower <= value <= upper
        for value, lower, upper in numeric
    ):
        raise ValueError("content generate bounded execution values drifted")
    return {
        "key": key,
        "authorities": parsed_authorities,
        "sourceRefs": source_refs,
        "factRefs": fact_refs,
    }


class ContentGenerateHostService:
    """Incomplete content capability host: exact input lineage only."""

    executor_identity = "ecommerce-growth-content-generate-host"

    @staticmethod
    def _review_receipt(transaction, scope, authorities, source_values):
        handoff_ref = authorities["handoff"]
        rows = transaction.execute(
            """SELECT request_hash,response,target_receipt_ref
                FROM public.ecommerce_growth_runtime_command_receipt
                WHERE org_id=%s AND project_id=%s
                  AND operation_id='ecommerce_growth_review_advance'
                  AND response->'handoffRef'->>'resourceId'=%s""",
            (*scope.key, handoff_ref.resource_id),
        ).fetchall()
        if len(rows) != 1:
            raise ValueError("content generate Review authority is not unique")
        response = rows[0]["response"]
        if type(response) is not dict or set(response) != _CONTENT_REVIEW_RECEIPT_FIELDS:
            raise ValueError("content generate Review Receipt shape drifted")
        response_ref = InvestigationExactRef.model_validate(response["receiptRef"])
        target_ref = InvestigationExactRef.model_validate(rows[0]["target_receipt_ref"])
        for raw_ref, parsed_ref in (
            (response["receiptRef"], response_ref),
            (rows[0]["target_receipt_ref"], target_ref),
        ):
            if (
                parsed_ref.resource_type != "ReviewDecisionReceipt"
                or type(parsed_ref.revision) is not int
                or parsed_ref.receipt_id != parsed_ref.resource_id
                or parsed_ref.model_dump(
                    mode="json", by_alias=True, exclude_none=True
                )
                != raw_ref
            ):
                raise ValueError("content generate Review Receipt exact ref drifted")
        body = {name: value for name, value in response.items() if name != "receiptRef"}
        expected_receipt_ref = {
            "resourceType": "ReviewDecisionReceipt",
            "resourceId": rows[0]["target_receipt_ref"]["resourceId"],
            "revision": 1,
            "contentHash": _analysis_command_hash(body),
            "receiptId": rows[0]["target_receipt_ref"]["resourceId"],
        }
        expected_artifacts = [item["artifactRef"] for item in response.get("artifactBindings", [])]
        if (
            response.get("receiptRef") != expected_receipt_ref
            or rows[0]["target_receipt_ref"] != expected_receipt_ref
            or response.get("requestHash") != rows[0]["request_hash"]
            or response.get("decision") != "ACCEPT"
            or response.get("returnStage") is not None
            or type(response.get("replayed")) is not bool
            or response.get("sideEffects") != _REVIEW_SIDE_EFFECTS
            or type(response["sideEffects"].get("externalEffectsAllowed")) is not bool
            or any(
                type(response["sideEffects"].get(name)) is not int
                for name in _REVIEW_SIDE_EFFECTS
                if name != "externalEffectsAllowed"
            )
            or response.get("handoffRef")
            != handoff_ref.model_dump(mode="json", by_alias=True, exclude_none=True)
            or response.get("taskRef")
            != authorities["task"].model_dump(mode="json", by_alias=True, exclude_none=True)
            or response.get("briefRef")
            != authorities["brief"].model_dump(mode="json", by_alias=True, exclude_none=True)
            or response.get("growthPlanRef")
            != authorities["growth_plan"].model_dump(
                mode="json", by_alias=True, exclude_none=True
            )
            or expected_artifacts != source_values
        ):
            raise ValueError("content generate Review exact lineage drifted")
        return response

    @staticmethod
    def _task_brief(transaction, scope, authorities, source_values) -> None:
        task_ref = authorities["task"]
        brief_ref = authorities["brief"]
        task = transaction.execute(
            """SELECT task_type,title,description,priority,goal,selection_ref,
                       policy_revision,request_hash
                FROM public.aip_task
                WHERE org_id=%s AND project_id=%s AND task_id=%s FOR SHARE""",
            (*scope.key, task_ref.resource_id),
        ).fetchone()
        head = transaction.execute(
            """SELECT task_id,current_revision,version FROM public.aip_task_brief_head
                WHERE org_id=%s AND project_id=%s AND brief_id=%s FOR SHARE""",
            (*scope.key, brief_ref.resource_id),
        ).fetchone()
        brief = transaction.execute(
            """SELECT task_id,brief_type,schema_ref,spec,content_hash,lifecycle,created_by
                FROM public.aip_task_brief_revision
                WHERE org_id=%s AND project_id=%s AND brief_id=%s AND revision=%s""",
            (*scope.key, brief_ref.resource_id, brief_ref.revision),
        ).fetchone()
        receipt = transaction.execute(
            """SELECT request_hash,result_ref,created_by
                FROM public.aip_production_contract_receipt
                WHERE org_id=%s AND project_id=%s AND operation='task_brief.create'
                  AND result_ref->>'resourceId'=%s""",
            (*scope.key, brief_ref.resource_id),
        ).fetchone()
        if task is None or head is None or brief is None or receipt is None:
            raise ValueError("content generate Task/Brief authority is missing")
        task_payload = {
            "type": task["task_type"],
            "title": task["title"],
            "description": task["description"],
            "priority": int(task["priority"]),
            "goal": task["goal"],
            "selectionRef": task["selection_ref"],
            "policyRevision": task["policy_revision"],
        }
        expected_task_ref = {
            "resourceType": "Task",
            "resourceId": task_ref.resource_id,
            "revision": 1,
            "contentHash": "sha256:" + _analysis_command_hash(task_payload).removeprefix("sha256:"),
        }
        expected_brief_hash = _analysis_command_hash(
            {
                "briefType": brief["brief_type"],
                "schemaRef": brief["schema_ref"],
                "spec": brief["spec"],
            }
        ).removeprefix("sha256:")
        expected_brief_ref = {
            "resourceType": "TaskBriefRevision",
            "resourceId": brief_ref.resource_id,
            "revision": brief_ref.revision,
            "contentHash": expected_brief_hash,
        }
        goal = task["goal"]
        spec = brief["spec"]
        expected_handoff = authorities["handoff"].model_dump(
            mode="json", by_alias=True, exclude_none=True
        )
        expected_growth_plan = authorities["growth_plan"].model_dump(
            mode="json", by_alias=True, exclude_none=True
        )
        owner_result_ref = receipt["result_ref"]
        owner_result_ref_valid = (
            type(owner_result_ref) is dict
            and set(owner_result_ref)
            == {"resourceType", "resourceId", "revision", "contentHash"}
            and owner_result_ref.get("resourceType") == "TaskBriefRevision"
            and type(owner_result_ref.get("resourceId")) is str
            and type(owner_result_ref.get("revision")) is int
            and type(owner_result_ref.get("contentHash")) is str
            and re.fullmatch(r"[0-9a-f]{64}", owner_result_ref["contentHash"])
            is not None
            and budget_canonical_hash(owner_result_ref)
            == budget_canonical_hash(expected_brief_ref)
        )
        if (
            task_ref.model_dump(mode="json", by_alias=True, exclude_none=True)
            != expected_task_ref
            or task["request_hash"] != expected_task_ref["contentHash"].removeprefix("sha256:")
            or int(head["current_revision"]) != brief_ref.revision
            or int(head["version"]) != brief_ref.revision
            or head["task_id"] != task_ref.resource_id
            or brief["task_id"] != task_ref.resource_id
            or brief["brief_type"] != "content_campaign"
            or brief["lifecycle"] != "draft"
            or brief["content_hash"] != expected_brief_hash
            or brief_ref.content_hash != "sha256:" + expected_brief_hash
            or brief["created_by"] != "ecommerce-growth-review-host"
            or not owner_result_ref_valid
            or receipt["created_by"] != "ecommerce-growth-review-host"
            or receipt["request_hash"]
            != _analysis_command_hash(
                {
                    "taskId": task_ref.resource_id,
                    "briefType": brief["brief_type"],
                    "schemaRef": brief["schema_ref"],
                    "spec": spec,
                }
            ).removeprefix("sha256:")
            or type(goal) is not dict
            or type(spec) is not dict
            or set(spec) != _CONTENT_BRIEF_SPEC_FIELDS
            or goal.get("sourceHandoffRef") != expected_handoff
            or spec.get("sourceHandoffRef") != expected_handoff
            or goal.get("growthPlanRef") != expected_growth_plan
            or spec.get("growthPlanRef") != expected_growth_plan
            or goal.get("artifactRefs") != source_values
            or spec.get("artifactRefs") != source_values
            or spec.get("taskRef")
            != task_ref.model_dump(mode="json", by_alias=True, exclude_none=True)
            or spec.get("externalPublicationRequested") is not False
        ):
            raise ValueError("content generate Task/Brief exact lineage drifted")

    @staticmethod
    def _agent_capability_authority(transaction, scope, authorities):
        agent_ref = authorities["agent_instance"]
        plan_ref = authorities["responsibility_plan"]
        capability_ref = authorities["capability"]
        agent_row = transaction.execute(
            """SELECT i.*,t.content_hash FROM public.aip_agent_instance i
                JOIN public.aip_agent_template_revision t
                  ON t.template_id=i.template_id AND t.revision=i.template_revision
                WHERE i.org_id=%s AND i.project_id=%s AND i.instance_id=%s
                FOR SHARE OF i""",
            (*scope.key, agent_ref.resource_id),
        ).fetchone()
        if agent_row is None:
            raise ValueError("content generate AgentInstance authority is missing")
        agent = AipAgentRegistryStore._instance_from_row(scope, agent_row)
        expected_agent_ref = {
            "resourceType": "AgentInstanceRevision",
            "resourceId": agent.instance_id,
            "revision": agent.version,
            "contentHash": "sha256:" + agent.instance_ref.content_hash,
        }
        if (
            agent.status is not AgentInstanceStatus.ACTIVE
            or agent_ref.model_dump(mode="json", by_alias=True, exclude_none=True)
            != expected_agent_ref
        ):
            raise ValueError("content generate AgentInstance authority drifted")

        head = transaction.execute(
            """SELECT current_revision,version
                 FROM public.aip_responsibility_plan_head
                WHERE org_id=%s AND project_id=%s AND plan_id=%s FOR SHARE""",
            (*scope.key, plan_ref.resource_id),
        ).fetchone()
        if head is None:
            raise ValueError("content generate ResponsibilityPlan authority is missing")
        plan_row = transaction.execute(
            """SELECT profile,template_ref,slots,merge_decisions,
                      profile_recommendation_ref,profile_confirmation_id,merge_policy_ref,
                      merge_decision_receipt_ids,content_hash,lifecycle
                 FROM public.aip_responsibility_plan_revision
                WHERE org_id=%s AND project_id=%s AND plan_id=%s AND revision=%s""",
            (*scope.key, plan_ref.resource_id, plan_ref.revision),
        ).fetchone()
        if plan_row is None:
            raise ValueError("content generate ResponsibilityPlan revision is missing")
        raw_plan_content = {
            "profile": plan_row["profile"],
            "templateRef": plan_row["template_ref"],
            "slots": plan_row["slots"],
            "mergeDecisions": plan_row["merge_decisions"],
            "profileRecommendationRef": plan_row["profile_recommendation_ref"],
            "profileConfirmationId": plan_row["profile_confirmation_id"],
            "mergePolicyRef": plan_row["merge_policy_ref"],
            "mergeDecisionReceiptIds": plan_row["merge_decision_receipt_ids"],
        }
        plan = AipProductionContractStore().get_responsibility_plan(
            scope, plan_ref.resource_id, plan_ref.revision, conn=transaction
        )
        expected_plan_ref = {
            "resourceType": "ResponsibilityPlanRevision",
            "resourceId": plan.plan_id,
            "revision": plan.revision,
            "contentHash": "sha256:" + plan.content_hash,
        }
        matching_slots = [
            slot
            for slot in plan.slots
            if slot.assignee.kind is AssigneeKind.AGENT_INSTANCE
            and slot.assignee.resource_id == agent.instance_id
            and slot.assignee.version == agent.version
            and capability_ref.resource_id in slot.required_capability_ids
        ]
        if (
            type(head["current_revision"]) is not int
            or type(head["version"]) is not int
            or head["current_revision"] != plan_ref.revision
            or head["version"] != plan_ref.revision
            or plan.version != head["version"]
            or production_contract_canonical_hash(raw_plan_content)
            != plan_row["content_hash"]
            or plan.content_hash != plan_row["content_hash"]
            or plan.lifecycle is not BriefLifecycle.FROZEN
            or plan.readiness is not ContractReadiness.READY
            or plan.coverage is not Coverage.COMPLETE
            or plan.blockers
            or plan.uncovered_slots
            or not matching_slots
            or plan_ref.model_dump(mode="json", by_alias=True, exclude_none=True)
            != expected_plan_ref
        ):
            raise ValueError("content generate ResponsibilityPlan authority drifted")

        capability_row = transaction.execute(
            """SELECT capability.*,
                      (SELECT max(candidate.revision)
                         FROM public.aip_capability_revision candidate
                        WHERE candidate.capability_id=capability.capability_id
                          AND candidate.lifecycle='published') AS latest_published_revision
                 FROM public.aip_capability_revision capability
                WHERE capability.capability_id=%s AND capability.revision=%s""",
            (capability_ref.resource_id, capability_ref.revision),
        ).fetchone()
        if capability_row is None:
            raise ValueError("content generate Capability authority is missing")
        capability = AipCapabilityRegistry._from_row(capability_row)
        expected_capability_ref = {
            "resourceType": "CapabilityRevision",
            "resourceId": capability.capability_id,
            "revision": capability.revision,
            "contentHash": "sha256:" + capability.content_hash,
        }
        if (
            capability.lifecycle is not TemplateLifecycle.PUBLISHED
            or capability.readiness is not CapabilityReadiness.AVAILABLE
            or capability.readiness_reasons
            or type(capability_row["latest_published_revision"]) is not int
            or capability_row["latest_published_revision"] != capability.revision
            or capability_ref.model_dump(mode="json", by_alias=True, exclude_none=True)
            != expected_capability_ref
        ):
            raise ValueError("content generate Capability authority drifted")
        return agent, capability

    @staticmethod
    def _route_budget_approval_authority(
        transaction, scope, authorities, *, upper_bound_fen: int
    ) -> tuple[ModelRouteRevision, datetime]:
        route_ref = authorities["model_route"]
        route_head = transaction.execute(
            """SELECT current_revision,version FROM public.aip_model_route_head
                WHERE org_id=%s AND project_id=%s AND model_route_id=%s FOR SHARE""",
            (*scope.key, route_ref.resource_id),
        ).fetchone()
        route_row = transaction.execute(
            """SELECT content_hash,lifecycle,payload
                 FROM public.aip_model_route_revision
                WHERE org_id=%s AND project_id=%s AND model_route_id=%s AND revision=%s""",
            (*scope.key, route_ref.resource_id, route_ref.revision),
        ).fetchone()
        if route_head is None or route_row is None:
            raise ValueError("content generate ModelRoute authority is missing")
        route_payload = AipModelRuntimeStore._load(route_row["payload"])
        route = ModelRouteRevision.model_validate(route_payload)
        route_content = {
            name: value
            for name, value in route_payload.items()
            if name not in AipModelRuntimeStore._META_FIELDS
        }
        expected_route_ref = {
            "resourceType": "ModelRouteRevision",
            "resourceId": route.route_id,
            "revision": route.revision,
            "contentHash": "sha256:" + route.content_hash,
        }
        if (
            type(route_head["current_revision"]) is not int
            or type(route_head["version"]) is not int
            or type(route_payload.get("revision")) is not int
            or route_payload.get("revision") != route_ref.revision
            or route_payload.get("tenant")
            != {"orgId": scope.org_id, "projectId": scope.project_id}
            or (route.tenant.org_id, route.tenant.project_id) != scope.key
            or route_head["current_revision"] != route_ref.revision
            or route_head["version"] != route_ref.revision
            or route_row["content_hash"] != route.content_hash
            or route_row["lifecycle"] != route.lifecycle.value
            or model_runtime_canonical_hash(route_content) != route.content_hash
            or route.lifecycle is not ModelRuntimeLifecycle.ACTIVE
            or "content_campaign" not in route.task_types
            or route.strategy is not RouteStrategy.FAILOVER
            or len(route.candidates) != 1
            or route.required_input_modality is not ModelModality.TEXT
            or route.required_output_modality is not ModelModality.TEXT
            or authorities["capability"].resource_id
            not in route.required_capabilities
            or route_ref.model_dump(mode="json", by_alias=True, exclude_none=True)
            != expected_route_ref
        ):
            raise ValueError("content generate ModelRoute authority drifted")

        checked = transaction.execute(
            "SELECT clock_timestamp() AS checked_at"
        ).fetchone()
        if checked is None or not isinstance(checked.get("checked_at"), datetime):
            raise ValueError("content generate authority cutoff is unavailable")
        budget = AipBudgetReservationStore()
        refs = {
            name: BudgetExactRef.model_validate(
                authorities[name].model_dump(
                    mode="json", by_alias=True, exclude_none=True
                )
            )
            for name in ("task", "budget", "pricing", "approval")
        }
        try:
            budget._budget_authority(
                transaction, scope, refs["budget"], checked["checked_at"]
            )
            budget._price_authority(
                transaction, scope, refs["pricing"], checked["checked_at"]
            )
            budget._approval_authority(
                transaction,
                scope,
                refs["approval"],
                checked["checked_at"],
                task_ref=refs["task"],
                operation_id="ecommerce_growth_content_generate",
                upper_bound_minor=upper_bound_fen,
            )
        except BudgetReservationError as exc:
            raise ValueError("content generate Budget/Approval authority drifted") from exc
        return route, checked["checked_at"]

    @staticmethod
    def _resolution_capacity_authority(
        transaction,
        scope,
        authorities,
        *,
        route: ModelRouteRevision,
        checked_at: datetime,
        max_input_tokens: int,
        max_output_tokens: int,
    ):
        capacity_ref = authorities["capacity_reservation"]
        capacity = transaction.execute(
            """SELECT r.reservation_id,r.pool_id,r.pool_revision,r.agent_run_id,
                      r.request_hash,r.request_units,r.token_units,r.status,
                      r.created_at AS reservation_created_at,r.expires_at,
                      h.current_revision,h.version AS head_version,
                      p.content_hash AS pool_content_hash,p.route_ref,p.model_ref,p.provider_ref,
                      p.route_id,p.route_revision,p.route_hash,
                      p.model_id,p.model_revision,p.model_hash,
                      p.provider_id,p.provider_revision,p.provider_hash,
                      p.max_concurrency,p.max_token_units,p.token_unit_per_reservation,
                      p.lease_seconds,p.lifecycle AS pool_lifecycle
                 FROM public.aip_model_capacity_reservation r
                 JOIN public.aip_model_capacity_pool_head h
                   ON h.org_id=r.org_id AND h.project_id=r.project_id
                  AND h.pool_id=r.pool_id
                 JOIN public.aip_model_capacity_pool_revision p
                   ON p.org_id=r.org_id AND p.project_id=r.project_id
                  AND p.pool_id=r.pool_id AND p.revision=r.pool_revision
                WHERE r.org_id=%s AND r.project_id=%s AND r.reservation_id=%s
                FOR SHARE OF r,h""",
            (*scope.key, capacity_ref.resource_id),
        ).fetchone()
        if capacity is None:
            raise ValueError("content generate CapacityReservation authority is missing")

        route_ref = authorities["model_route"]
        pool_refs = {
            "route": AipModelRuntimeStore._load(capacity["route_ref"]),
            "model": AipModelRuntimeStore._load(capacity["model_ref"]),
            "provider": AipModelRuntimeStore._load(capacity["provider_ref"]),
        }
        pool_content = {
            "poolId": capacity["pool_id"],
            "revision": capacity["pool_revision"],
            "routeRef": pool_refs["route"],
            "modelRef": pool_refs["model"],
            "providerRef": pool_refs["provider"],
            "maxConcurrency": capacity["max_concurrency"],
            "maxTokenUnits": capacity["max_token_units"],
            "tokenUnitPerReservation": capacity["token_unit_per_reservation"],
            "leaseSeconds": capacity["lease_seconds"],
            "lifecycle": capacity["pool_lifecycle"],
        }
        try:
            pool = CapacityPoolRevisionCreate.model_validate(pool_content)
        except ValueError as exc:
            raise ValueError("content generate CapacityPool authority drifted") from exc
        selected_model_ref = pool.model_ref
        selected_provider_ref = pool.provider_ref
        expected_capacity_ref = {
            "resourceType": "CapacityReservation",
            "resourceId": capacity["reservation_id"],
            "revision": 1,
            "contentHash": "sha256:" + capacity["request_hash"],
        }
        split_refs = {
            "route": (
                capacity["route_id"], capacity["route_revision"], capacity["route_hash"]
            ),
            "model": (
                capacity["model_id"], capacity["model_revision"], capacity["model_hash"]
            ),
            "provider": (
                capacity["provider_id"],
                capacity["provider_revision"],
                capacity["provider_hash"],
            ),
        }
        expected_split_refs = {
            "route": (route_ref.resource_id, route_ref.revision, route_ref.content_hash.removeprefix("sha256:")),
            "model": (selected_model_ref.asset_id, selected_model_ref.revision, selected_model_ref.content_hash),
            "provider": (selected_provider_ref.asset_id, selected_provider_ref.revision, selected_provider_ref.content_hash),
        }
        exact_resolution = tuple(
            value
            for name in ("route", "model", "provider")
            for value in expected_split_refs[name]
        )
        expected_request_hash = AipModelCapacityReservationGate._request_hash(
            capacity["agent_run_id"],
            exact_resolution,
            capacity["pool_id"],
            capacity["pool_revision"],
            capacity["token_unit_per_reservation"],
        )
        if (
            type(capacity["pool_revision"]) is not int
            or type(capacity["current_revision"]) is not int
            or type(capacity["head_version"]) is not int
            or capacity["current_revision"] != capacity["pool_revision"]
            or capacity["head_version"] != capacity["pool_revision"]
            or capacity["pool_lifecycle"] != "active"
            or capacity_pool_canonical_hash(pool_content) != capacity["pool_content_hash"]
            or split_refs != expected_split_refs
            or any(
                capacity_pool_canonical_hash(pool_refs[name])
                != capacity_pool_canonical_hash(
                    {
                        "assetType": kind,
                        "assetId": expected_split_refs[name][0],
                        "revision": expected_split_refs[name][1],
                        "contentHash": expected_split_refs[name][2],
                    }
                )
                for name, kind in (
                    ("route", "ModelRouteRevision"),
                    ("model", "RegisteredModelRevision"),
                    ("provider", "ProviderInstanceRevision"),
                )
            )
            or capacity["status"] != "reserved"
            or capacity["reservation_created_at"] > checked_at
            or capacity["expires_at"] <= checked_at
            or type(capacity["request_units"]) is not int
            or capacity["request_units"] != 1
            or type(capacity["token_units"]) is not int
            or capacity["token_units"] != capacity["token_unit_per_reservation"]
            or max_input_tokens + max_output_tokens > capacity["token_units"]
            or capacity["request_hash"] != expected_request_hash
            or capacity_ref.model_dump(mode="json", by_alias=True, exclude_none=True)
            != expected_capacity_ref
        ):
            raise ValueError("content generate CapacityReservation authority drifted")

        def read_runtime_asset(table: str, id_column: str, ref, model, id_field: str):
            row = transaction.execute(
                f"""SELECT content_hash,lifecycle,payload FROM public.{table}
                    WHERE org_id=%s AND project_id=%s AND {id_column}=%s AND revision=%s""",
                (*scope.key, ref.asset_id, ref.revision),
            ).fetchone()
            if row is None:
                raise ValueError("content generate ModelRuntime dependency is missing")
            payload = AipModelRuntimeStore._load(row["payload"])
            try:
                item = model.model_validate(payload)
            except ValueError as exc:
                raise ValueError("content generate ModelRuntime dependency drifted") from exc
            content = {
                name: value
                for name, value in payload.items()
                if name not in AipModelRuntimeStore._META_FIELDS
            }
            if (
                payload.get("tenant")
                != {"orgId": scope.org_id, "projectId": scope.project_id}
                or type(payload.get("revision")) is not int
                or payload.get("revision") != ref.revision
                or getattr(item, id_field) != ref.asset_id
                or item.content_hash != ref.content_hash
                or row["content_hash"] != ref.content_hash
                or row["lifecycle"] != item.lifecycle.value
                or model_runtime_canonical_hash(content) != ref.content_hash
                or item.lifecycle is not ModelRuntimeLifecycle.ACTIVE
            ):
                raise ValueError("content generate ModelRuntime dependency drifted")
            return item

        model = read_runtime_asset(
            "aip_registered_model_revision",
            "registered_model_id",
            selected_model_ref,
            RegisteredModelRevision,
            "registered_model_id",
        )
        provider = read_runtime_asset(
            "aip_provider_instance_revision",
            "provider_instance_id",
            selected_provider_ref,
            ProviderInstanceRevision,
            "provider_instance_id",
        )
        policy = read_runtime_asset(
            "aip_runtime_policy_revision",
            "policy_id",
            route.runtime_policy_ref,
            RuntimePolicyRevision,
            "policy_id",
        )
        first_candidate = route.candidates[0].model
        pricing_ref = authorities["pricing"]
        if (
            len(route.candidates) != 1
            or selected_model_ref != first_candidate
            or model.provider != selected_provider_ref
            or model.price_snapshot_ref.asset_id != pricing_ref.resource_id
            or model.price_snapshot_ref.revision != pricing_ref.revision
            or model.price_snapshot_ref.content_hash
            != pricing_ref.content_hash.removeprefix("sha256:")
            or route.required_input_modality not in model.input_modalities
            or route.required_output_modality not in model.output_modalities
            or not set(route.required_capabilities).issubset(model.capabilities)
            or max_input_tokens + max_output_tokens > model.context_window
            or policy.kill_switch_enabled
        ):
            raise ValueError("content generate ModelRoute resolution drifted")

        def require_gate(ref, expected_target, target_type: str) -> None:
            row = transaction.execute(
                """SELECT target_ref,status,decision_hash,invalidated_by,decided_at,expires_at
                     FROM public.aip_release_gate_decision
                    WHERE org_id=%s AND project_id=%s AND decision_id=%s""",
                (*scope.key, ref.asset_id),
            ).fetchone()
            target = AipModelRuntimeStore._load(row["target_ref"]) if row else None
            expected = {
                "assetType": target_type,
                "assetId": expected_target.asset_id,
                "revision": str(expected_target.revision),
                "contentHash": expected_target.content_hash,
            }
            if (
                row is None
                or ref.revision != 1
                or row["decision_hash"] != ref.content_hash
                or row["status"] != "passed"
                or row["invalidated_by"] is not None
                or not row["decided_at"] <= checked_at < row["expires_at"]
                or capacity_pool_canonical_hash(target)
                != capacity_pool_canonical_hash(expected)
            ):
                raise ValueError("content generate EvalGate authority drifted")

        require_gate(
            route.eval_gate_ref,
            evaluation_candidate_ref(route),
            "model_route",
        )
        require_gate(
            model.eval_gate_ref,
            evaluation_candidate_ref(model),
            "registered_model",
        )
        health = transaction.execute(
            """SELECT status,provider_ref,observed_at,expires_at
                 FROM public.aip_provider_health_observation
                WHERE org_id=%s AND project_id=%s
                  AND provider_ref->>'assetId'=%s
                ORDER BY observed_at DESC,observation_id DESC LIMIT 1""",
            (*scope.key, selected_provider_ref.asset_id),
        ).fetchone()
        if (
            health is None
            or health["status"] != "healthy"
            or not health["observed_at"] <= checked_at < health["expires_at"]
            or capacity_pool_canonical_hash(
                AipModelRuntimeStore._load(health["provider_ref"])
            )
            != capacity_pool_canonical_hash(
                selected_provider_ref.model_dump(mode="json", by_alias=True)
            )
        ):
            raise ValueError("content generate Provider health authority drifted")

        run = transaction.execute(
            """SELECT agent_run_id,task_id,instance_id,instance_version,skill_binding_id,
                      skill_ref,model_route_ref,policy_ref,status,version
                 FROM public.aip_agent_run
                WHERE org_id=%s AND project_id=%s AND agent_run_id=%s FOR SHARE""",
            (*scope.key, capacity["agent_run_id"]),
        ).fetchone()
        agent_ref = authorities["agent_instance"]
        expected_run_route_ref = {
            "assetType": "ModelRouteRevision",
            "assetId": route.route_id,
            "revision": route.revision,
            "contentHash": route.content_hash,
        }
        if (
            run is None
            or run["status"] != "running"
            or run["task_id"] != authorities["task"].resource_id
            or run["instance_id"] != agent_ref.resource_id
            or type(run["instance_version"]) is not int
            or run["instance_version"] != agent_ref.revision
            or capacity_pool_canonical_hash(AipModelRuntimeStore._load(run["model_route_ref"]))
            != capacity_pool_canonical_hash(expected_run_route_ref)
            or capacity_pool_canonical_hash(AipModelRuntimeStore._load(run["policy_ref"]))
            != capacity_pool_canonical_hash(route.runtime_policy_ref.model_dump(mode="json", by_alias=True))
        ):
            raise ValueError("content generate AgentRun capacity lineage drifted")
        return model, provider, policy, run

    @staticmethod
    def _binding_authority(
        transaction,
        scope,
        authorities,
        *,
        route,
        provider,
        policy,
        run,
        capability,
        checked_at,
    ) -> None:
        row = transaction.execute(
            """SELECT b.*,s.content_hash AS skill_content_hash,
                      s.lifecycle AS skill_lifecycle,s.publication_tenant,
                      s.model_route_ref AS skill_model_route_ref,
                      s.runtime_policy_ref AS skill_runtime_policy_ref,
                      s.release_gate_ref AS skill_release_gate_ref,
                      s.required_capabilities
                 FROM public.aip_skill_binding b
                 JOIN public.aip_skill_template_revision s
                   ON s.skill_id=b.skill_id AND s.revision=b.skill_revision
                WHERE b.org_id=%s AND b.project_id=%s AND b.binding_id=%s
                FOR SHARE OF b""",
            (*scope.key, run["skill_binding_id"]),
        ).fetchone()
        if row is None:
            raise ValueError("content generate SkillBinding authority is missing")

        def strict_versioned_ref(value):
            raw = AipModelRuntimeStore._load(value)
            if not isinstance(raw, dict) or type(raw.get("revision")) is not int:
                raise ValueError("content generate Binding exact ref drifted")
            parsed = VersionedAssetRef.model_validate(raw)
            canonical = parsed.model_dump(mode="json", by_alias=True)
            if capacity_pool_canonical_hash(raw) != capacity_pool_canonical_hash(canonical):
                raise ValueError("content generate Binding exact ref drifted")
            return parsed

        for field in (
            "model_route_ref",
            "runtime_policy_ref",
            "eval_gate_ref",
            "budget_policy_ref",
        ):
            strict_versioned_ref(row[field])
        binding_row = dict(row)
        binding_row["content_hash"] = row["skill_content_hash"]
        try:
            binding = AipSkillRegistry._binding_from_row(scope, binding_row)
        except ValueError as exc:
            raise ValueError("content generate SkillBinding authority drifted") from exc
        capability_ids = binding.capability_binding_ids
        capability_rows = transaction.execute(
            """SELECT binding_id,capability_ref,status,health,version,
                      provider_ref,model_route_ref,runtime_policy_ref,eval_gate_ref,
                      eval_contract_ref,license_evidence_refs,data_dependency_refs,
                      tool_dependency_refs,budget_policy_ref,allow_degraded,
                      dependency_snapshot_hash,operational_readiness,readiness_reasons,
                      observed_at,last_evaluated_at,readiness_expires_at
                 FROM public.aip_capability_binding
                WHERE org_id=%s AND project_id=%s AND binding_id=ANY(%s)
                ORDER BY binding_id FOR SHARE""",
            (*scope.key, capability_ids),
        ).fetchall()
        skill_ref = strict_versioned_ref(run["skill_ref"])
        skill_route_ref = strict_versioned_ref(row["skill_model_route_ref"])
        skill_policy_ref = strict_versioned_ref(row["skill_runtime_policy_ref"])
        skill_gate_ref = strict_versioned_ref(row["skill_release_gate_ref"])
        def asset_ref(asset_type, asset_id, revision, content_hash):
            return VersionedAssetRef(
                assetType=asset_type,
                assetId=asset_id,
                revision=revision,
                contentHash=content_hash,
            )

        route_ref = asset_ref(
            "ModelRouteRevision", route.route_id, route.revision, route.content_hash
        )
        provider_ref = asset_ref(
            "ProviderInstanceRevision",
            provider.provider_instance_id,
            provider.revision,
            provider.content_hash,
        )
        capability_ref = asset_ref(
            "CapabilityRevision",
            capability.capability_id,
            capability.revision,
            capability.content_hash,
        )
        policy_ref = route.runtime_policy_ref
        gate_ref = route.eval_gate_ref
        budget_policy_ref = policy.budget_policy_ref
        if (
            not run["skill_binding_id"]
            or not capability_ids
            or len(capability_ids) != len(set(capability_ids))
            or any(not item.strip() for item in capability_ids)
            or binding.instance_id != authorities["agent_instance"].resource_id
            or binding.status != "active"
            or type(row["version"]) is not int
            or binding.readiness is not CapabilityReadiness.AVAILABLE
            or binding.readiness_reasons
            or binding.last_evaluated_at is None
            or binding.readiness_expires_at is None
            or not binding.last_evaluated_at <= checked_at < binding.readiness_expires_at
            or skill_ref != binding.skill
            or row["skill_lifecycle"] != "published"
            or row["publication_tenant"]
            != {"orgId": scope.org_id, "projectId": scope.project_id}
            or skill_route_ref != route_ref
            or skill_policy_ref != policy_ref
            or skill_gate_ref != gate_ref
            or binding.dependencies.model_route_ref != route_ref
            or binding.dependencies.runtime_policy_ref != policy_ref
            or binding.dependencies.eval_gate_ref != gate_ref
            or binding.dependencies.budget_policy_ref != budget_policy_ref
            or binding.budget_policy_ref != budget_policy_ref
            or len(capability_rows) != len(capability_ids)
            or {item["binding_id"] for item in capability_rows}
            != set(capability_ids)
            or binding.dependency_snapshot_hash
            != AipSkillBindingReadinessService.snapshot_hash(binding, capability_rows)
        ):
            raise ValueError("content generate SkillBinding authority drifted")

        required_capabilities = row["required_capabilities"]
        if (
            not isinstance(required_capabilities, list)
            or any(not isinstance(item, str) or not item.strip() for item in required_capabilities)
            or len(required_capabilities) != len(set(required_capabilities))
        ):
            raise ValueError("content generate Skill capability coverage drifted")
        provided_capabilities = set()
        for item in capability_rows:
            capability_item = strict_versioned_ref(item["capability_ref"])
            for field in (
                "provider_ref",
                "model_route_ref",
                "runtime_policy_ref",
                "eval_gate_ref",
                "eval_contract_ref",
                "budget_policy_ref",
            ):
                strict_versioned_ref(item[field])
            for field in ("data_dependency_refs", "tool_dependency_refs"):
                raw_refs = AipModelRuntimeStore._load(item[field])
                if not isinstance(raw_refs, list):
                    raise ValueError("content generate Binding exact ref drifted")
                for raw_ref in raw_refs:
                    strict_versioned_ref(raw_ref)
            provided_capabilities.add(capability_item.asset_id)
            if (
                item["status"] != "active"
                or item["health"] != "healthy"
                or type(item["version"]) is not int
                or item["operational_readiness"] != "available"
                or item["readiness_reasons"]
                or item["observed_at"] is None
                or item["last_evaluated_at"] is None
                or item["readiness_expires_at"] is None
                or item["observed_at"] > checked_at
                or not item["last_evaluated_at"] <= checked_at < item["readiness_expires_at"]
            ):
                raise ValueError("content generate CapabilityBinding authority drifted")
        if (
            capability.capability_id not in required_capabilities
            or not set(required_capabilities).issubset(provided_capabilities)
        ):
            raise ValueError("content generate Skill capability coverage drifted")

        matching = [
            item
            for item in capability_rows
            if strict_versioned_ref(item["capability_ref"]) == capability_ref
        ]
        if len(matching) != 1:
            raise ValueError("content generate CapabilityBinding authority drifted")
        cap_row = matching[0]
        try:
            dependencies = AipCapabilityBindingService._dependencies_from_row(cap_row)
        except ValueError as exc:
            raise ValueError("content generate CapabilityBinding authority drifted") from exc
        if (
            dependencies.provider_ref != provider_ref
            or dependencies.model_route_ref != route_ref
            or dependencies.runtime_policy_ref != policy_ref
            or dependencies.eval_gate_ref != gate_ref
            or dependencies.budget_policy_ref != budget_policy_ref
            or cap_row["dependency_snapshot_hash"]
            != AipBindingReadinessService.snapshot_hash(
                capability_ref, dependencies
            )
        ):
            raise ValueError("content generate CapabilityBinding authority drifted")

    def revalidate(self, *, transaction, scope, dispatch, command):
        parsed = _strict_content_generate_command(command)
        if dispatch.operation_id != "ecommerce_growth_content_generate":
            raise ValueError("content generate dispatch operation drifted")
        source_values = [
            ref.model_dump(mode="json", by_alias=True, exclude_none=True)
            for ref in parsed["sourceRefs"]
        ]
        review = self._review_receipt(
            transaction, scope, parsed["authorities"], source_values
        )
        self._task_brief(transaction, scope, parsed["authorities"], source_values)
        ReviewAdvanceHostService._revalidate_growth_plan(
            transaction=transaction,
            scope=scope,
            command={
                "growthPlanRef": parsed["authorities"]["growth_plan"].model_dump(
                    mode="json", by_alias=True, exclude_none=True
                )
            },
        )
        _agent, capability = self._agent_capability_authority(
            transaction, scope, parsed["authorities"]
        )
        route, checked_at = self._route_budget_approval_authority(
            transaction,
            scope,
            parsed["authorities"],
            upper_bound_fen=command["upperBoundFen"],
        )
        _model, provider, policy, run = self._resolution_capacity_authority(
            transaction,
            scope,
            parsed["authorities"],
            route=route,
            checked_at=checked_at,
            max_input_tokens=command["maxInputTokens"],
            max_output_tokens=command["maxOutputTokens"],
        )
        self._binding_authority(
            transaction,
            scope,
            parsed["authorities"],
            route=route,
            provider=provider,
            policy=policy,
            run=run,
            capability=capability,
            checked_at=checked_at,
        )
        return {
            "key": parsed["key"],
            "reviewReceiptRef": review["receiptRef"],
        }


class InvestigationDescribeAdapter(_ExplicitRuntimeAdapter):
    SPEC = _AdapterSpec("ecommerce_growth_investigation_describe", ("channel", "business_entity", "source_readiness"), ("receiptRef",))


class CasePutAdapter(_ExplicitRuntimeAdapter):
    SPEC = _AdapterSpec("ecommerce_growth_case_put", ("profile", "channel", "business_entity", "task_brief"), ("receiptRef",))


class SchedulePutAdapter(_ExplicitRuntimeAdapter):
    SPEC = _AdapterSpec("ecommerce_growth_schedule_put", ("case", "schedule_policy", "approval"), ("receiptRef",))


class ScheduleTriggerAdapter(_ExplicitRuntimeAdapter):
    SPEC = _AdapterSpec("ecommerce_growth_schedule_trigger", ("schedule_policy", "occurrence", "execution_epoch"), ("occurrenceRef",))


class DataFulfillAdapter(_ExplicitRuntimeAdapter):
    SPEC = _AdapterSpec("ecommerce_growth_data_fulfill", ("case", "run", "checkpoint", "channel", "business_entity", "data_requirement", "source_readiness", "mapping", "facts", "evidence"), ("requirementRef", "fulfillmentRef"))


class AnalysisAdvanceAdapter(_ExplicitRuntimeAdapter):
    SPEC = _AdapterSpec("ecommerce_growth_analysis_advance", ("occurrence", "case", "profile", "run", "plan", "task_run", "checkpoint", "data_requirement", "fulfillment", "facts", "evidence"), ("receiptRef",))


class ReviewAdvanceAdapter(_ExplicitRuntimeAdapter):
    SPEC = _AdapterSpec("ecommerce_growth_review_advance", ("occurrence", "case", "run", "analysis_receipt", "plan", "growth_plan", "review_issue", "eval_report", "artifacts", "responsibility"), ("receiptRef",))


class ContentGenerateAdapter(_ExplicitRuntimeAdapter):
    SPEC = _AdapterSpec("ecommerce_growth_content_generate", ("task", "task_brief", "growth_plan", "artifacts", "fact_sources", "responsibility", "capability", "model_route", "pricing", "approval", "budget", "capacity"), ("receiptRef",))


class ContentReviewAdapter(_ExplicitRuntimeAdapter):
    SPEC = _AdapterSpec("ecommerce_growth_content_review", ("artifact", "task", "task_brief", "review_issue", "reviewer_authority"), ("receiptRef",))


RUNTIME_ADAPTER_TYPES = (
    InvestigationDescribeAdapter,
    CasePutAdapter,
    SchedulePutAdapter,
    ScheduleTriggerAdapter,
    DataFulfillAdapter,
    AnalysisAdvanceAdapter,
    ReviewAdvanceAdapter,
    ContentGenerateAdapter,
    ContentReviewAdapter,
)


__all__ = [adapter.__name__ for adapter in RUNTIME_ADAPTER_TYPES] + [
    "RUNTIME_ADAPTER_TYPES",
    "InvestigationDescribeHostService",
    "CasePutHostService",
    "SchedulePutHostService",
    "ScheduleTriggerHostService",
    "DataRequirementRequestHostService",
    "DataFulfillHostService",
    "AnalysisAdvanceHostService",
    "ReviewAdvanceHostService",
    "TransactionBoundConnectFactory",
    "TrustedEcommerceGrowthDomainService",
]

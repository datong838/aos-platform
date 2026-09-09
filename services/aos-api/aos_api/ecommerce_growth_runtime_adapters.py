"""Nine explicit trusted-host adapters for the ecommerce growth package."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import json
import math
import re
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
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
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
from aos_api.aip_business_investigation_compile_saga import BusinessInvestigationCompilationReceiptStore
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
REVIEW_RECEIPT_NAMESPACE = UUID("b42b2d81-8e5f-4c3b-ad29-7f6e5d4c3b2a")
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

    def _review_lineage(self, *, transaction, scope, command, occurred_at):
        raise ValueError("review ACCEPT requires existing Handoff, Task and Brief authority")

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
        targets = [receipt.get(key) for key in self.SPEC.receipt_keys if receipt.get(key) is not None]
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

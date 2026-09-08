"""Nine explicit trusted-host adapters for the ecommerce growth package."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import json
from typing import Any, Mapping, Protocol
from uuid import UUID
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
from aos_api.ecommerce_business_investigation_data_command import (
    EcommerceBusinessInvestigationDataCommandService,
    RequestBusinessInvestigationMissingDataCommand,
)
from aos_api.ecommerce_business_investigation_run import BusinessInvestigationRunStore
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
    "TransactionBoundConnectFactory",
    "TrustedEcommerceGrowthDomainService",
]

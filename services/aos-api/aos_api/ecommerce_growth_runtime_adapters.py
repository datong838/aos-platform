"""Nine explicit trusted-host adapters for the ecommerce growth package."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import Any, Mapping, Protocol

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
from aos_api.ecommerce_business_investigation_case_selection import (
    CatalogCanonicalProfileSelectionSource,
    PostgresCanonicalShopSelectionSource,
)
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


class _AlreadyValidatedCaseSelection:
    def verify_case_refs(self, *_args, **_kwargs) -> None:
        return None


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
    "CasePutHostService",
    "SchedulePutHostService",
    "TransactionBoundConnectFactory",
    "TrustedEcommerceGrowthDomainService",
]

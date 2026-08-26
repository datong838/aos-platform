"""BI-W6-01 receipt-first bridge from the domain Run to canonical AIP compilation."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import Any, Literal, Protocol, Self

import psycopg
from psycopg.types.json import Jsonb
from pydantic import Field, field_validator, model_validator

from aos_api.aip_business_investigation_compiler import (
    BusinessInvestigationCompilation,
    BusinessInvestigationProfileCompiler,
    CompileBusinessInvestigationRequest,
)
from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.db import connect as db_connect
from aos_api.ecommerce_business_investigation_run import (
    BusinessInvestigationRunControl,
    BusinessInvestigationRunLifecycle,
    BusinessInvestigationRunView,
)
from aos_api.tenant_scope import TenantScope


SCHEMA_VERSION = "aos.aip.business-investigation-compilation-receipt/v1"
SHA256 = r"^sha256:[0-9a-f]{64}$"


def _canonical_hash(value: object, *, prefixed: bool = True) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    return f"sha256:{digest}" if prefixed else digest


def _stable_id(prefix: str, value: object) -> str:
    return f"{prefix}-{_canonical_hash(value, prefixed=False)}"


def _aip_ref(ref: InvestigationExactRef, expected_type: str) -> ExactRevisionRef:
    if ref.resource_type != expected_type or not isinstance(ref.revision, int):
        raise BusinessInvestigationCompileConflict(f"{expected_type} exact ref is required")
    if not ref.content_hash.startswith("sha256:"):
        raise BusinessInvestigationCompileConflict("domain exact hash representation drifted")
    return ExactRevisionRef(
        resource_type=ref.resource_type,
        resource_id=ref.resource_id,
        revision=ref.revision,
        content_hash=ref.content_hash.removeprefix("sha256:"),
    )


class BusinessInvestigationCompilationReceipt(AipContractModel):
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    tenant: TenantContext
    receipt_id: str = Field(min_length=1, max_length=200)
    command_id: str = Field(min_length=1, max_length=200)
    request_hash: str = Field(pattern=SHA256)
    run_ref: InvestigationExactRef
    task_id: str = Field(min_length=1, max_length=200)
    plan_ref: ExactRevisionRef
    profile_ref: ExactRevisionRef
    logic_ref: ExactRevisionRef
    skill_binding_set_ref: ExactRevisionRef
    responsibility_plan_ref: ExactRevisionRef
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    stage_compilation_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    compilation_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    runtime_authorized: Literal[False] = False
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("createdAt must include timezone")
        return value

    @model_validator(mode="after")
    def _exact_lineage(self) -> Self:
        expected = (
            (self.run_ref.resource_type, "BusinessInvestigationRun", "runRef"),
            (self.plan_ref.resource_type, "PlanRevision", "planRef"),
            (self.profile_ref.resource_type, "InvestigationProfileRevision", "profileRef"),
            (self.logic_ref.resource_type, "LogicRevision", "logicRef"),
            (self.skill_binding_set_ref.resource_type, "SkillBindingSetRevision", "skillBindingSetRef"),
            (self.responsibility_plan_ref.resource_type, "ResponsibilityPlanRevision", "responsibilityPlanRef"),
        )
        for actual, required, label in expected:
            if actual != required:
                raise ValueError(f"{label} must reference {required}")
        return self

    @property
    def exact_ref(self) -> InvestigationExactRef:
        return InvestigationExactRef(
            resource_type="BusinessInvestigationCompilationReceipt",
            resource_id=self.receipt_id,
            revision=1,
            content_hash=_canonical_hash(
                self.model_dump(mode="json", by_alias=True)
            ),
        )


@dataclass(frozen=True, slots=True)
class BusinessInvestigationCompilationReceiptWrite:
    authority: BusinessInvestigationCompilationReceipt
    replayed: bool


class BusinessInvestigationCompileConflict(RuntimeError):
    pass


ConnectFactory = Callable[..., AbstractContextManager[Any]]


class CompilationReceiptAuthority(Protocol):
    def get(
        self, scope: TenantScope, command_id: str
    ) -> BusinessInvestigationCompilationReceipt | None: ...

    def record(
        self, scope: TenantScope, receipt: BusinessInvestigationCompilationReceipt
    ) -> BusinessInvestigationCompilationReceiptWrite: ...


class BusinessInvestigationCompilationReceiptStore:
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def get(
        self, scope: TenantScope, command_id: str
    ) -> BusinessInvestigationCompilationReceipt | None:
        if not command_id.strip() or len(command_id) > 200:
            raise BusinessInvestigationCompileConflict("command id must be non-empty and bounded")
        try:
            with self._connect_factory(scope) as conn:
                row = conn.execute(
                    """SELECT receipt_data FROM aip_business_investigation_compile_receipt
                    WHERE org_id=%s AND project_id=%s AND command_id=%s""",
                    (scope.org_id, scope.project_id, command_id),
                ).fetchone()
        except psycopg.Error as exc:
            raise BusinessInvestigationCompileConflict(
                "canonical compilation Receipt read failed closed"
            ) from exc
        return None if row is None else BusinessInvestigationCompilationReceipt.model_validate(row["receipt_data"])

    def record(
        self, scope: TenantScope, receipt: BusinessInvestigationCompilationReceipt
    ) -> BusinessInvestigationCompilationReceiptWrite:
        if (receipt.tenant.org_id, receipt.tenant.project_id) != scope.key:
            raise BusinessInvestigationCompileConflict("Receipt tenant does not match scope")
        payload = receipt.model_dump(mode="json", by_alias=True)
        try:
            with self._connect_factory(scope) as conn:
                row = conn.execute(
                    """SELECT receipt_data,replayed
                    FROM aip_business_investigation_compile_receipt_biw6_001(%s,%s,%s,%s)""",
                    (receipt.command_id, receipt.request_hash, receipt.receipt_id, Jsonb(payload)),
                ).fetchone()
                conn.commit()
        except psycopg.Error as exc:
            raise BusinessInvestigationCompileConflict(
                "canonical compilation Receipt write failed closed"
            ) from exc
        if row is None:
            raise BusinessInvestigationCompileConflict(
                "canonical compilation Receipt returned no authority"
            )
        return BusinessInvestigationCompilationReceiptWrite(
            authority=BusinessInvestigationCompilationReceipt.model_validate(row["receipt_data"]),
            replayed=bool(row["replayed"]),
        )


class BusinessInvestigationCompileSaga:
    def __init__(
        self,
        compiler: BusinessInvestigationProfileCompiler,
        receipts: CompilationReceiptAuthority,
    ) -> None:
        self._compiler = compiler
        self._receipts = receipts

    def execute(
        self,
        scope: TenantScope,
        actor: str,
        trigger_idempotency_key: str,
        run: BusinessInvestigationRunView,
        request: CompileBusinessInvestigationRequest,
    ) -> BusinessInvestigationCompilationReceiptWrite:
        actor = actor.strip()
        trigger_idempotency_key = trigger_idempotency_key.strip()
        if not actor or not trigger_idempotency_key or len(trigger_idempotency_key) > 200:
            raise BusinessInvestigationCompileConflict(
                "actor and trigger idempotency key are required and bounded"
            )
        domain_run_ref = self._validate_inputs(scope, run, request)
        command_material = {
            "tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
            "runRef": domain_run_ref.model_dump(mode="json", by_alias=True),
            "triggerIdempotencyKey": trigger_idempotency_key,
        }
        command_id = _stable_id("bi-compile", command_material)
        request_material = {
            "commandId": command_id,
            "runRef": domain_run_ref.model_dump(mode="json", by_alias=True),
            "compileRequest": request.model_dump(mode="json", by_alias=True),
        }
        request_hash = _canonical_hash(request_material)
        existing = self._receipts.get(scope, command_id)
        if existing is not None:
            if (
                (existing.tenant.org_id, existing.tenant.project_id) != scope.key
                or existing.command_id != command_id
                or existing.run_ref != domain_run_ref
                or existing.task_id != request.task_id
            ):
                raise BusinessInvestigationCompileConflict(
                    "canonical compilation Receipt lineage drifted"
                )
            if existing.request_hash != request_hash:
                raise BusinessInvestigationCompileConflict(
                    "compilation command request hash conflict"
                )
            return BusinessInvestigationCompilationReceiptWrite(
                authority=existing, replayed=True
            )

        compilation = self._compiler.compile(
            scope, actor, command_id, request
        )
        self._validate_compilation(scope, request, compilation)
        receipt = BusinessInvestigationCompilationReceipt(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            receipt_id=_stable_id(
                "bi-compilation-receipt",
                {"commandId": command_id, "requestHash": request_hash},
            ),
            command_id=command_id,
            request_hash=request_hash,
            run_ref=domain_run_ref,
            task_id=compilation.task_id,
            plan_ref=compilation.plan_ref,
            profile_ref=compilation.profile_ref,
            logic_ref=compilation.logic_ref,
            skill_binding_set_ref=compilation.skill_binding_set_ref,
            responsibility_plan_ref=compilation.responsibility_plan_ref,
            input_hash=compilation.input_hash,
            stage_compilation_hash=compilation.stage_compilation_hash,
            compilation_hash=compilation.compilation_hash,
            created_at=compilation.created_at,
        )
        result = self._receipts.record(scope, receipt)
        if result.authority != receipt:
            raise BusinessInvestigationCompileConflict(
                "canonical compilation Receipt drifted"
            )
        return result

    @staticmethod
    def _validate_inputs(
        scope: TenantScope,
        run: BusinessInvestigationRunView,
        request: CompileBusinessInvestigationRequest,
    ) -> InvestigationExactRef:
        authority = run.authority
        state = run.state
        if (authority.tenant.org_id, authority.tenant.project_id) != scope.key or (
            state.tenant.org_id,
            state.tenant.project_id,
        ) != scope.key:
            raise BusinessInvestigationCompileConflict("Run tenant does not match scope")
        if authority.run_id != state.run_id:
            raise BusinessInvestigationCompileConflict("Run authority/state identity drifted")
        if (
            state.lifecycle is not BusinessInvestigationRunLifecycle.PREPARING
            or state.control is not BusinessInvestigationRunControl.RUNNING
        ):
            raise BusinessInvestigationCompileConflict(
                "Run must be PREPARING and RUNNING"
            )
        if authority.calculated_content_hash() != authority.content_hash:
            raise BusinessInvestigationCompileConflict("Run authority content hash drifted")
        domain_run_ref = InvestigationExactRef(
            resource_type="BusinessInvestigationRun",
            resource_id=authority.run_id,
            revision=authority.version,
            content_hash=authority.content_hash,
        )
        if request.run_ref != _aip_ref(domain_run_ref, "BusinessInvestigationRun"):
            raise BusinessInvestigationCompileConflict("compile request Run exact ref drifted")
        if request.case_ref != _aip_ref(
            authority.case_ref, "BusinessInvestigationCaseRevision"
        ):
            raise BusinessInvestigationCompileConflict("compile request Case exact ref drifted")
        if request.profile.analysis_type != authority.analysis_type.value:
            raise BusinessInvestigationCompileConflict("compile request analysis type drifted")
        return domain_run_ref

    @staticmethod
    def _validate_compilation(
        scope: TenantScope,
        request: CompileBusinessInvestigationRequest,
        compilation: BusinessInvestigationCompilation,
    ) -> None:
        if (compilation.tenant.org_id, compilation.tenant.project_id) != scope.key:
            raise BusinessInvestigationCompileConflict("compilation tenant drifted")
        expected = (
            (compilation.task_id, request.task_id, "task"),
            (compilation.case_ref, request.case_ref, "Case exact ref"),
            (compilation.run_ref, request.run_ref, "Run exact ref"),
            (compilation.task_brief_ref, request.task_brief_ref, "TaskBrief exact ref"),
            (compilation.profile_ref, request.profile.exact_ref, "Profile exact ref"),
            (compilation.logic_ref, request.profile.logic_ref, "Logic exact ref"),
            (
                compilation.skill_binding_set_ref,
                request.profile.skill_binding_set_ref,
                "SkillBindingSet exact ref",
            ),
            (
                compilation.responsibility_plan_ref,
                request.profile.responsibility_plan_ref,
                "ResponsibilityPlan exact ref",
            ),
        )
        for actual, wanted, label in expected:
            if actual != wanted:
                raise BusinessInvestigationCompileConflict(f"compilation {label} drifted")
        if compilation.runtime_authorized:
            raise BusinessInvestigationCompileConflict(
                "compilation must not authorize runtime"
            )

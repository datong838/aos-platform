"""Application service for the AIP-1 canonical task runtime."""
from __future__ import annotations

from aos_api.aip_task_models import (
    ApprovePlanRevisionRequest,
    CreatePlanRevisionRequest,
    CreateTaskRequest,
    CreateTaskRunRequest,
    PlanRevisionSnapshot,
    RunControlRequest,
    RunControlResult,
    TaskRunSnapshot,
    TaskSnapshot,
)
from aos_api.aip_task_store import AipTaskStore
from aos_api.auth import Principal
from aos_api.public_contracts import TaskStatus
from aos_api.tenant_scope import TenantScope


class AipTaskService:
    def __init__(self, store: AipTaskStore) -> None:
        self.store = store

    @staticmethod
    def scope(principal: Principal) -> TenantScope:
        return TenantScope(principal.org_id, principal.project_id)

    def create_task(
        self, principal: Principal, idempotency_key: str, body: CreateTaskRequest
    ) -> TaskSnapshot:
        return self.store.create_task(
            self.scope(principal), principal.subject, idempotency_key, body
        )

    def list_tasks(
        self, principal: Principal, status: TaskStatus | None, limit: int
    ) -> list[TaskSnapshot]:
        return self.store.list_tasks(self.scope(principal), status=status, limit=limit)

    def create_plan(
        self,
        principal: Principal,
        task_id: str,
        idempotency_key: str,
        body: CreatePlanRevisionRequest,
    ) -> PlanRevisionSnapshot:
        return self.store.create_plan(
            self.scope(principal), principal.subject, task_id, idempotency_key, body
        )

    def approve_plan(
        self,
        principal: Principal,
        task_id: str,
        revision: int,
        body: ApprovePlanRevisionRequest,
    ) -> PlanRevisionSnapshot:
        return self.store.approve_plan(
            self.scope(principal),
            principal.subject,
            task_id,
            revision,
            body.expected_task_version,
            body.expected_content_hash,
        )

    def create_run(
        self,
        principal: Principal,
        task_id: str,
        idempotency_key: str,
        body: CreateTaskRunRequest,
    ) -> TaskRunSnapshot:
        return self.store.create_run(
            self.scope(principal), principal.subject, task_id, idempotency_key, body
        )

    def start_run(
        self,
        principal: Principal,
        run_id: str,
        idempotency_key: str,
        body: RunControlRequest,
    ) -> RunControlResult:
        return self.store.start_run(
            self.scope(principal),
            run_id,
            expected_run_version=body.expected_run_version,
            expected_task_version=body.expected_task_version,
            actor=principal.subject,
            idempotency_key=idempotency_key,
            reason=body.reason,
        )

    def pause_run(
        self, principal: Principal, run_id: str, idempotency_key: str, body: RunControlRequest
    ) -> RunControlResult:
        return self.store.pause_run(
            self.scope(principal),
            run_id,
            expected_run_version=body.expected_run_version,
            expected_task_version=body.expected_task_version,
            actor=principal.subject,
            idempotency_key=idempotency_key,
            reason=body.reason,
        )

    def resume_run(
        self, principal: Principal, run_id: str, idempotency_key: str, body: RunControlRequest
    ) -> RunControlResult:
        return self.store.resume_run(
            self.scope(principal),
            run_id,
            expected_run_version=body.expected_run_version,
            expected_task_version=body.expected_task_version,
            actor=principal.subject,
            idempotency_key=idempotency_key,
            reason=body.reason,
        )

    def cancel_run(
        self, principal: Principal, run_id: str, idempotency_key: str, body: RunControlRequest
    ) -> RunControlResult:
        return self.store.cancel_run(
            self.scope(principal),
            run_id,
            expected_run_version=body.expected_run_version,
            expected_task_version=body.expected_task_version,
            actor=principal.subject,
            idempotency_key=idempotency_key,
            reason=body.reason,
        )

    def rollback_run(
        self, principal: Principal, run_id: str, idempotency_key: str, body: RunControlRequest
    ) -> RunControlResult:
        return self.store.rollback_run(
            self.scope(principal),
            run_id,
            expected_run_version=body.expected_run_version,
            expected_task_version=body.expected_task_version,
            actor=principal.subject,
            idempotency_key=idempotency_key,
            reason=body.reason,
        )

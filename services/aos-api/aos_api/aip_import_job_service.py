"""Tenant-scoped, receipt-first authority for governed import candidates.

Applying a job creates a reversible control-plane candidate only. It never
executes supplied source, resolves secrets, calls a Provider, publishes a
canonical asset, or mutates a business system.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from typing import Any

from aos_api.aip_contracts import ResourceRef, TenantContext
from aos_api.aip_import_preview import preview_import
from aos_api.aip_marketplace_import_contracts import (
    ApplyImportJobRequest,
    ApproveImportJobRequest,
    CreateImportJobRequest,
    ImportCandidate,
    ImportJob,
    ImportJobListResponse,
    ImportJobMutationResponse,
    ImportJobReceipt,
    ImportJobStatus,
    RollbackImportJobRequest,
)
from aos_api.auth import Principal
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

ConnectFactory = Callable[..., AbstractContextManager[Any]]


class AipImportJobError(RuntimeError):
    code = "AIP_IMPORT_JOB_ERROR"


class AipImportJobNotFound(AipImportJobError):
    code = "AIP_IMPORT_JOB_NOT_FOUND"


class AipImportJobConflict(AipImportJobError):
    code = "AIP_IMPORT_JOB_CONFLICT"


class AipImportJobBlocked(AipImportJobError):
    code = "AIP_IMPORT_JOB_BLOCKED"


class AipImportJobPersistenceError(AipImportJobError):
    code = "AIP_IMPORT_JOB_PERSISTENCE_ERROR"


class AipImportJobService:
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def create(
        self,
        principal: Principal,
        request: CreateImportJobRequest,
        *,
        idempotency_key: str,
        occurred_at: datetime | None = None,
    ) -> ImportJobMutationResponse:
        now = occurred_at or datetime.now(UTC)
        preview = preview_import(principal, request.preview_request)
        if preview.preview_id != request.expected_preview_id or preview.content_hash != request.expected_content_hash:
            raise AipImportJobConflict("import preview changed; regenerate the exact preview")
        if preview.status == "blocked":
            raise AipImportJobBlocked("blocked import preview cannot create a job")
        scope = TenantScope(principal.org_id, principal.project_id)
        operation = "import_job.create"
        request_hash = self._hash({"actor": principal.subject, "request": request})
        try:
            with self._connect_factory(scope) as conn:
                self._lock(conn, scope, operation, idempotency_key)
                replay = self._receipt_row(conn, scope, operation, idempotency_key)
                if replay:
                    self._require_replay(replay, request_hash)
                    return self._response(scope, conn, replay)
                existing = conn.execute(
                    """SELECT * FROM aip_import_job
                       WHERE org_id=%s AND project_id=%s AND preview_id=%s""",
                    (*scope.key, preview.preview_id),
                ).fetchone()
                if existing is not None:
                    raise AipImportJobConflict("this exact preview already has an import job")
                job_id = f"aip-import-{uuid.uuid4().hex}"
                conn.execute(
                    """INSERT INTO aip_import_job
                       (org_id,project_id,job_id,preview_id,preview_content_hash,kind,
                        target_id,display_name,request_payload,conflict_decisions,
                        status,version,created_by,created_at,updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,
                               'awaiting_approval',1,%s,%s,%s)""",
                    (
                        *scope.key,
                        job_id,
                        preview.preview_id,
                        preview.content_hash,
                        request.preview_request.kind.value,
                        request.preview_request.mapping.target_id,
                        request.preview_request.mapping.display_name,
                        self._json(request.preview_request),
                        self._json(request.conflict_decisions),
                        principal.subject,
                        now,
                        now,
                    ),
                )
                receipt = self._insert_receipt(conn, scope, operation, idempotency_key, request_hash, job_id, principal.subject, now)
                response = self._response(scope, conn, receipt)
                conn.commit()
                return response
        except AipImportJobError:
            raise
        except Exception as exc:
            raise AipImportJobPersistenceError("import job create failed") from exc

    def approve(
        self,
        scope: TenantScope,
        job_id: str,
        request: ApproveImportJobRequest,
        *,
        actor: str,
        idempotency_key: str,
        occurred_at: datetime | None = None,
    ) -> ImportJobMutationResponse:
        return self._transition(
            scope,
            job_id,
            request,
            actor=actor,
            idempotency_key=idempotency_key,
            from_status=ImportJobStatus.AWAITING_APPROVAL,
            to_status=ImportJobStatus.APPROVED,
            operation="import_job.approve",
            occurred_at=occurred_at,
        )

    def apply(
        self,
        scope: TenantScope,
        job_id: str,
        request: ApplyImportJobRequest,
        *,
        actor: str,
        idempotency_key: str,
        occurred_at: datetime | None = None,
    ) -> ImportJobMutationResponse:
        return self._transition(
            scope,
            job_id,
            request,
            actor=actor,
            idempotency_key=idempotency_key,
            from_status=ImportJobStatus.APPROVED,
            to_status=ImportJobStatus.APPLIED,
            operation="import_job.apply",
            occurred_at=occurred_at,
        )

    def rollback(
        self,
        scope: TenantScope,
        job_id: str,
        request: RollbackImportJobRequest,
        *,
        actor: str,
        idempotency_key: str,
        occurred_at: datetime | None = None,
    ) -> ImportJobMutationResponse:
        return self._transition(
            scope,
            job_id,
            request,
            actor=actor,
            idempotency_key=idempotency_key,
            from_status=ImportJobStatus.APPLIED,
            to_status=ImportJobStatus.ROLLED_BACK,
            operation="import_job.rollback",
            occurred_at=occurred_at,
        )

    def get(self, scope: TenantScope, job_id: str) -> ImportJob:
        try:
            with self._connect_factory(scope) as conn:
                return self._job_from_row(scope, self._job_row(conn, scope, job_id))
        except AipImportJobError:
            raise
        except Exception as exc:
            raise AipImportJobPersistenceError("import job read failed") from exc

    def list(self, scope: TenantScope, *, limit: int = 100) -> ImportJobListResponse:
        try:
            with self._connect_factory(scope) as conn:
                rows = conn.execute(
                    """SELECT * FROM aip_import_job WHERE org_id=%s AND project_id=%s
                       ORDER BY updated_at DESC,job_id LIMIT %s""",
                    (*scope.key, limit),
                ).fetchall()
            items = [self._job_from_row(scope, row) for row in rows]
            return ImportJobListResponse(
                tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
                items=items,
                count=len(items),
            )
        except Exception as exc:
            raise AipImportJobPersistenceError("import job list failed") from exc

    def _transition(
        self,
        scope: TenantScope,
        job_id: str,
        request: Any,
        *,
        actor: str,
        idempotency_key: str,
        from_status: ImportJobStatus,
        to_status: ImportJobStatus,
        operation: str,
        occurred_at: datetime | None,
    ) -> ImportJobMutationResponse:
        now = occurred_at or datetime.now(UTC)
        request_hash = self._hash({"actor": actor, "jobId": job_id, "request": request})
        try:
            with self._connect_factory(scope) as conn:
                self._lock(conn, scope, operation, idempotency_key)
                replay = self._receipt_row(conn, scope, operation, idempotency_key)
                if replay:
                    self._require_replay(replay, request_hash)
                    return self._response(scope, conn, replay)
                row = self._job_row(conn, scope, job_id)
                if row is None:
                    raise AipImportJobNotFound("import job not found")
                if row["version"] != request.expected_version or row["status"] != from_status.value:
                    raise AipImportJobConflict("import job version or lifecycle changed")
                if operation == "import_job.approve":
                    conn.execute(
                        """UPDATE aip_import_job SET status='approved',version=version+1,
                           approval_evidence_ref=%s::jsonb,approval_reason=%s,approved_by=%s,updated_at=%s
                           WHERE org_id=%s AND project_id=%s AND job_id=%s""",
                        (self._json(request.test_evidence_ref), request.decision_reason, actor, now, *scope.key, job_id),
                    )
                elif operation == "import_job.apply":
                    candidate_id = f"aip-import-candidate-{uuid.uuid4().hex}"
                    payload = row["request_payload"]
                    candidate_hash = self._hash({"jobId": job_id, "request": payload})
                    resource_type = "ImportedAgentCandidate" if row["kind"] == "agent" else "ImportedCapabilityCandidate"
                    created_ref = ResourceRef(resource_type=resource_type, resource_id=candidate_id, revision="1", authority="postgresql")
                    source_ref = payload["source"]["sourceRef"]
                    conn.execute(
                        """INSERT INTO aip_import_candidate
                           (org_id,project_id,candidate_id,job_id,kind,target_id,display_name,
                            status,source_ref,payload,content_hash,created_at)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,'active',%s::jsonb,%s::jsonb,%s,%s)""",
                        (*scope.key, candidate_id, job_id, row["kind"], row["target_id"], row["display_name"],
                         self._json(source_ref), self._json(payload), candidate_hash, now),
                    )
                    conn.execute(
                        """UPDATE aip_import_job SET status='applied',version=version+1,
                           created_refs=%s::jsonb,applied_by=%s,updated_at=%s
                           WHERE org_id=%s AND project_id=%s AND job_id=%s""",
                        (self._json([created_ref]), actor, now, *scope.key, job_id),
                    )
                else:
                    candidate = self._candidate_row(conn, scope, job_id)
                    if candidate is None or candidate["status"] != "active":
                        raise AipImportJobConflict("active import candidate not found")
                    conn.execute(
                        """UPDATE aip_import_candidate SET status='rolled_back',rolled_back_at=%s
                           WHERE org_id=%s AND project_id=%s AND job_id=%s AND status='active'""",
                        (now, *scope.key, job_id),
                    )
                    conn.execute(
                        """UPDATE aip_import_job SET status='rolled_back',version=version+1,
                           compensated_refs=created_refs,rollback_reason=%s,updated_at=%s
                           WHERE org_id=%s AND project_id=%s AND job_id=%s""",
                        (request.reason, now, *scope.key, job_id),
                    )
                receipt = self._insert_receipt(conn, scope, operation, idempotency_key, request_hash, job_id, actor, now)
                response = self._response(scope, conn, receipt)
                conn.commit()
                return response
        except AipImportJobError:
            raise
        except Exception as exc:
            raise AipImportJobPersistenceError(f"{operation} failed") from exc

    @staticmethod
    def _job_row(conn: Any, scope: TenantScope, job_id: str):
        return conn.execute(
            "SELECT * FROM aip_import_job WHERE org_id=%s AND project_id=%s AND job_id=%s",
            (*scope.key, job_id),
        ).fetchone()

    @staticmethod
    def _candidate_row(conn: Any, scope: TenantScope, job_id: str):
        return conn.execute(
            "SELECT * FROM aip_import_candidate WHERE org_id=%s AND project_id=%s AND job_id=%s",
            (*scope.key, job_id),
        ).fetchone()

    @staticmethod
    def _receipt_row(conn: Any, scope: TenantScope, operation: str, key: str):
        return conn.execute(
            """SELECT * FROM aip_import_job_receipt
               WHERE org_id=%s AND project_id=%s AND operation=%s AND idempotency_key=%s""",
            (*scope.key, operation, key),
        ).fetchone()

    def _insert_receipt(self, conn: Any, scope: TenantScope, operation: str, key: str, request_hash: str, job_id: str, actor: str, now: datetime):
        return conn.execute(
            """INSERT INTO aip_import_job_receipt
               (org_id,project_id,receipt_id,operation,idempotency_key,request_hash,
                job_id,status,created_by,created_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,'applied',%s,%s) RETURNING *""",
            (*scope.key, f"aip-import-receipt-{uuid.uuid4().hex}", operation, key, request_hash, job_id, actor, now),
        ).fetchone()

    def _response(self, scope: TenantScope, conn: Any, receipt_row: Any) -> ImportJobMutationResponse:
        job_row = self._job_row(conn, scope, receipt_row["job_id"])
        candidate_row = self._candidate_row(conn, scope, receipt_row["job_id"])
        return ImportJobMutationResponse(
            job=self._job_from_row(scope, job_row),
            candidate=self._candidate_from_row(scope, candidate_row) if candidate_row else None,
            receipt=ImportJobReceipt(
                receipt_id=receipt_row["receipt_id"], operation=receipt_row["operation"],
                idempotency_key=receipt_row["idempotency_key"], request_hash=receipt_row["request_hash"],
                status=receipt_row["status"], created_by=receipt_row["created_by"], created_at=receipt_row["created_at"],
            ),
        )

    @staticmethod
    def _job_from_row(scope: TenantScope, row: Any) -> ImportJob:
        if row is None:
            raise AipImportJobNotFound("import job not found")
        return ImportJob(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            job_id=row["job_id"], preview_id=row["preview_id"], preview_content_hash=row["preview_content_hash"],
            kind=row["kind"], target_id=row["target_id"], display_name=row["display_name"], status=row["status"],
            conflict_decisions=row["conflict_decisions"], approval_evidence_ref=row["approval_evidence_ref"],
            approval_reason=row["approval_reason"], rollback_reason=row["rollback_reason"],
            created_refs=row["created_refs"], compensated_refs=row["compensated_refs"], version=row["version"],
            created_by=row["created_by"], approved_by=row["approved_by"], applied_by=row["applied_by"],
            created_at=row["created_at"], updated_at=row["updated_at"],
        )

    @staticmethod
    def _candidate_from_row(scope: TenantScope, row: Any) -> ImportCandidate:
        return ImportCandidate(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            candidate_id=row["candidate_id"], job_id=row["job_id"], kind=row["kind"], target_id=row["target_id"],
            display_name=row["display_name"], status=row["status"], source_ref=row["source_ref"],
            content_hash=row["content_hash"], created_at=row["created_at"], rolled_back_at=row["rolled_back_at"],
        )

    @staticmethod
    def _json(value: Any) -> str:
        def normalize(item: Any) -> Any:
            if hasattr(item, "model_dump"):
                return normalize(item.model_dump(mode="json", by_alias=True))
            if isinstance(item, dict):
                return {key: normalize(child) for key, child in item.items()}
            if isinstance(item, (list, tuple)):
                return [normalize(child) for child in item]
            return item

        return json.dumps(normalize(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

    @classmethod
    def _hash(cls, value: Any) -> str:
        return hashlib.sha256(cls._json(value).encode()).hexdigest()

    @staticmethod
    def _lock(conn: Any, scope: TenantScope, operation: str, key: str) -> None:
        if not key.strip() or len(key) > 200:
            raise ValueError("idempotency key must be 1..200 characters")
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"aip-import:{scope.org_id}:{scope.project_id}:{operation}:{key}",))

    @staticmethod
    def _require_replay(row: Any, expected_hash: str) -> None:
        if row["request_hash"] != expected_hash:
            raise AipImportJobConflict("idempotency key was reused with different content")


__all__ = [
    "AipImportJobBlocked", "AipImportJobConflict", "AipImportJobError",
    "AipImportJobNotFound", "AipImportJobPersistenceError", "AipImportJobService",
]

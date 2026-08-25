"""PostgreSQL authority store for W7-07 media Provider Jobs."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from aos_api.aip_media_provider_job_contracts import (
    MediaAssetDirection,
    IssueMediaAccessGrantRequest,
    MediaAccessGrant,
    MediaJobEventType,
    MediaJobStatus,
    MediaProviderBindingSnapshot,
    MediaProviderJob,
    MediaProviderJobEvent,
    MediaProviderJobListResponse,
    MediaProviderReceipt,
    MediaScanObservation,
    MediaScanVerdict,
    PrepareMediaProviderJobRequest,
    ProviderOperation,
    ProviderOperationResult,
    ServerOwnedMediaScanResult,
)
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope


class MediaProviderJobError(RuntimeError):
    code = "MEDIA_PROVIDER_JOB_ERROR"


class MediaProviderJobNotFound(MediaProviderJobError):
    code = "MEDIA_PROVIDER_JOB_NOT_FOUND"


class MediaProviderJobConflict(MediaProviderJobError):
    code = "MEDIA_PROVIDER_JOB_CONFLICT"


class MediaProviderJobDependencyBlocked(MediaProviderJobError):
    code = "MEDIA_PROVIDER_JOB_DEPENDENCY_BLOCKED"


class MediaProviderJobPersistenceError(MediaProviderJobError):
    code = "MEDIA_PROVIDER_JOB_PERSISTENCE_FAILED"


class AipMediaProviderJobStore:
    def __init__(self, *, connect_factory=db_connect) -> None:
        self._connect = connect_factory

    @staticmethod
    def _json(value: Any) -> str:
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json", by_alias=True)
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=lambda item: item.model_dump(mode="json", by_alias=True),
        )

    @classmethod
    def canonical_hash(cls, value: Any) -> str:
        return hashlib.sha256(cls._json(value).encode()).hexdigest()

    @staticmethod
    def _tenant(scope: TenantScope) -> dict[str, str]:
        return {"orgId": scope.org_id, "projectId": scope.project_id}

    def prepare_job(
        self,
        scope: TenantScope,
        actor: str,
        key: str,
        body: PrepareMediaProviderJobRequest,
        binding: MediaProviderBindingSnapshot,
        scans: list[ServerOwnedMediaScanResult],
    ) -> MediaProviderJob:
        if len(scans) != len(body.input_artifact_refs):
            raise MediaProviderJobDependencyBlocked("MEDIA_INPUT_SCAN_COUNT_DRIFTED")
        for artifact, scan in zip(body.input_artifact_refs, scans, strict=True):
            if scan.content_hash != artifact.content_hash:
                raise MediaProviderJobDependencyBlocked("MEDIA_INPUT_SCAN_HASH_DRIFTED")
            if scan.verdict is not MediaScanVerdict.PASSED:
                raise MediaProviderJobDependencyBlocked(
                    scan.findings[0].code if scan.findings else "MEDIA_INPUT_SCAN_NOT_PASSED"
                )
        payload = {
            "body": body.model_dump(mode="json", by_alias=True),
            "binding": binding.model_dump(mode="json", by_alias=True),
            "scans": [item.model_dump(mode="json", by_alias=True) for item in scans],
        }
        request_hash = self.canonical_hash(payload)
        try:
            with self._connect(scope) as conn:
                replay = self._replay(conn, scope, "prepare", key, request_hash)
                if replay is not None:
                    return self.get_job(scope, replay["resourceId"], conn=conn)
                job_id = f"media-job-{uuid.uuid4().hex[:24]}"
                scan_refs: list[ExactRevisionRef] = []
                now = datetime.now(UTC)
                for artifact, result in zip(body.input_artifact_refs, scans, strict=True):
                    observation = self._insert_scan(
                        conn, scope, actor, artifact, MediaAssetDirection.INPUT,
                        body.scan_policy_ref, body.scanner_ref, result,
                    )
                    scan_refs.append(
                        ExactRevisionRef(
                            resourceType="MediaScanObservation",
                            resourceId=observation.scan_id,
                            revision=1,
                            contentHash=observation.content_hash,
                        )
                    )
                conn.execute(
                    """INSERT INTO aip_media_provider_job(
                       org_id,project_id,job_id,task_run_ref,step_run_ref,binding_snapshot,
                       input_artifact_refs,input_scan_refs,scan_policy_ref,scanner_ref,
                       expected_output_modality,purpose,
                       data_classification,request_fingerprint,created_by,created_at)
                       VALUES(%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
                              %s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s)""",
                    (
                        *scope.key, job_id, self._json(body.task_run_ref),
                        self._json(body.step_run_ref), self._json(binding),
                        self._json(body.input_artifact_refs), self._json(scan_refs),
                        self._json(body.scan_policy_ref), self._json(body.scanner_ref),
                        body.expected_output_modality, body.purpose,
                        body.data_classification, request_hash, actor, now,
                    ),
                )
                event_hash = self.canonical_hash(
                    {"jobId": job_id, "sequence": 1, "eventType": "prepared", "status": "prepared"}
                )
                conn.execute(
                    """INSERT INTO aip_media_provider_job_event(
                       org_id,project_id,job_id,sequence,event_type,status,provider_receipt_ref,
                       blocker_codes,event_hash,actor,created_at)
                       VALUES(%s,%s,%s,1,'prepared','prepared',NULL,'[]'::jsonb,%s,%s,%s)""",
                    (*scope.key, job_id, event_hash, actor, now),
                )
                self._idempotency(
                    conn, scope, "prepare", key, request_hash,
                    {"resourceType": "MediaProviderJob", "resourceId": job_id},
                )
                conn.commit()
                return self.get_job(scope, job_id, conn=conn)
        except MediaProviderJobError:
            raise
        except Exception as exc:
            raise MediaProviderJobPersistenceError("media job preparation failed") from exc

    def _insert_scan(
        self,
        conn: Any,
        scope: TenantScope,
        actor: str,
        artifact_ref: ExactRevisionRef,
        direction: MediaAssetDirection,
        policy_ref: ExactRevisionRef,
        scanner_ref: ExactRevisionRef,
        result: ServerOwnedMediaScanResult,
    ) -> MediaScanObservation:
        scan_id = f"media-scan-{uuid.uuid4().hex[:24]}"
        conn.execute(
            """INSERT INTO aip_media_asset_scan_observation(
               org_id,project_id,scan_id,artifact_ref,direction,scan_policy_ref,scanner_ref,
               detected_mime,byte_size,content_hash,verdict,findings,created_by,created_at)
               VALUES(%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s::jsonb,%s,%s)""",
            (
                *scope.key, scan_id, self._json(artifact_ref), direction.value,
                self._json(policy_ref), self._json(scanner_ref), result.detected_mime,
                result.byte_size, result.content_hash, result.verdict.value,
                self._json(result.findings), actor, result.scanned_at,
            ),
        )
        return MediaScanObservation(
            tenant=self._tenant(scope), scanId=scan_id, artifactRef=artifact_ref,
            direction=direction, scanPolicyRef=policy_ref,
            detectedMime=result.detected_mime, byteSize=result.byte_size,
            contentHash=result.content_hash, verdict=result.verdict,
            findings=result.findings, scannerRef=scanner_ref, createdBy=actor,
            createdAt=result.scanned_at,
        )

    def record_scan_observation(
        self,
        scope: TenantScope,
        actor: str,
        artifact_ref: ExactRevisionRef,
        direction: MediaAssetDirection,
        policy_ref: ExactRevisionRef,
        scanner_ref: ExactRevisionRef,
        result: ServerOwnedMediaScanResult,
    ) -> MediaScanObservation:
        if result.content_hash != artifact_ref.content_hash:
            raise MediaProviderJobDependencyBlocked("MEDIA_SCAN_HASH_DRIFTED")
        try:
            with self._connect(scope) as conn:
                item = self._insert_scan(
                    conn, scope, actor, artifact_ref, direction,
                    policy_ref, scanner_ref, result,
                )
                conn.commit()
                return item
        except MediaProviderJobError:
            raise
        except Exception as exc:
            raise MediaProviderJobPersistenceError("media scan persistence failed") from exc

    def issue_access_grant(
        self,
        scope: TenantScope,
        body: IssueMediaAccessGrantRequest,
        *,
        token_hash: str,
        now: datetime | None = None,
    ) -> MediaAccessGrant:
        issued_at = now or datetime.now(UTC)
        if len(token_hash) != 64 or any(char not in "0123456789abcdef" for char in token_hash):
            raise MediaProviderJobConflict("MEDIA_ACCESS_TOKEN_HASH_INVALID")
        if body.expires_at <= issued_at:
            raise MediaProviderJobConflict("MEDIA_ACCESS_GRANT_EXPIRED")
        grant_id = f"media-access-grant-{uuid.uuid4().hex[:24]}"
        try:
            with self._connect(scope) as conn:
                conn.execute(
                    """INSERT INTO aip_media_access_grant(
                       org_id,project_id,grant_id,artifact_ref,principal_ref,purpose,marking,
                       license_ref,expires_at,token_hash,access_receipt_ref,created_at)
                       VALUES(%s,%s,%s,%s::jsonb,%s,%s,%s,%s::jsonb,%s,%s,%s::jsonb,%s)""",
                    (
                        *scope.key, grant_id, self._json(body.artifact_ref),
                        body.principal_ref, body.purpose, body.marking,
                        self._json(body.license_ref), body.expires_at, token_hash,
                        self._json(body.access_receipt_ref), issued_at,
                    ),
                )
                conn.commit()
        except MediaProviderJobError:
            raise
        except Exception as exc:
            raise MediaProviderJobPersistenceError("media access grant persistence failed") from exc
        return MediaAccessGrant(
            tenant=self._tenant(scope), grantId=grant_id, artifactRef=body.artifact_ref,
            principalRef=body.principal_ref, purpose=body.purpose, marking=body.marking,
            licenseRef=body.license_ref, expiresAt=body.expires_at, tokenHash=token_hash,
            accessReceiptRef=body.access_receipt_ref, createdAt=issued_at,
        )

    def record_operation(
        self,
        scope: TenantScope,
        actor: str,
        job_id: str,
        key: str,
        operation: ProviderOperation,
        result: ProviderOperationResult,
        *,
        expected_sequence: int,
    ) -> MediaProviderJob:
        payload = {
            "jobId": job_id,
            "operation": operation.value,
            "result": result.model_dump(mode="json", by_alias=True),
            "expectedSequence": expected_sequence,
        }
        request_hash = self.canonical_hash(payload)
        receipt_payload = {
            "jobId": job_id,
            "operation": operation.value,
            "outcome": result.status.value,
            "providerRequestIdHash": result.provider_request_id_hash,
            "outputArtifactRefs": [
                item.model_dump(mode="json", by_alias=True)
                for item in result.output_artifact_refs
            ],
            "usageReceiptRef": (
                result.usage_receipt_ref.model_dump(mode="json", by_alias=True)
                if result.usage_receipt_ref else None
            ),
            "observedAt": result.observed_at.isoformat(),
        }
        payload_hash = self.canonical_hash(receipt_payload)
        try:
            with self._connect(scope) as conn:
                replay = self._replay(conn, scope, operation.value, key, request_hash)
                if replay is not None:
                    return self.get_job(scope, job_id, conn=conn)
                if operation is ProviderOperation.WEBHOOK:
                    duplicate = conn.execute(
                        """SELECT receipt_id FROM aip_media_provider_receipt
                           WHERE org_id=%s AND project_id=%s AND job_id=%s
                             AND operation='webhook' AND payload_hash=%s""",
                        (*scope.key, job_id, payload_hash),
                    ).fetchone()
                    if duplicate is not None:
                        return self.get_job(scope, job_id, conn=conn)
                current = self._latest_event(conn, scope, job_id, lock=True)
                if current is None:
                    raise MediaProviderJobNotFound(job_id)
                if int(current["sequence"]) != expected_sequence:
                    raise MediaProviderJobConflict("MEDIA_JOB_SEQUENCE_CONFLICT")
                self._assert_transition(
                    MediaJobStatus(current["status"]), operation, result.status
                )
                receipt_id = f"media-provider-receipt-{uuid.uuid4().hex[:24]}"
                conn.execute(
                    """INSERT INTO aip_media_provider_receipt(
                       org_id,project_id,receipt_id,job_id,operation,outcome,
                       provider_request_id_hash,output_artifact_refs,usage_receipt_ref,
                       payload_hash,actor,observed_at)
                       VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s)""",
                    (
                        *scope.key, receipt_id, job_id, operation.value, result.status.value,
                        result.provider_request_id_hash, self._json(result.output_artifact_refs),
                        self._json(result.usage_receipt_ref) if result.usage_receipt_ref else None,
                        payload_hash, actor, result.observed_at,
                    ),
                )
                sequence = expected_sequence + 1
                event_type = self._event_type(operation)
                receipt_ref = ExactRevisionRef(
                    resourceType="MediaProviderReceipt", resourceId=receipt_id,
                    revision=1, contentHash=payload_hash,
                )
                event_payload = {
                    "jobId": job_id, "sequence": sequence,
                    "eventType": event_type.value, "status": result.status.value,
                    "providerReceiptRef": receipt_ref.model_dump(mode="json", by_alias=True),
                    "blockerCodes": result.blocker_codes,
                }
                event_hash = self.canonical_hash(event_payload)
                conn.execute(
                    """INSERT INTO aip_media_provider_job_event(
                       org_id,project_id,job_id,sequence,event_type,status,
                       provider_receipt_ref,blocker_codes,event_hash,actor,created_at)
                       VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s)""",
                    (
                        *scope.key, job_id, sequence, event_type.value, result.status.value,
                        self._json(receipt_ref), self._json(result.blocker_codes),
                        event_hash, actor, result.observed_at,
                    ),
                )
                self._idempotency(
                    conn, scope, operation.value, key, request_hash,
                    {"resourceType": "MediaProviderJobEvent", "resourceId": job_id,
                     "revision": sequence, "contentHash": event_hash},
                )
                conn.commit()
                return self.get_job(scope, job_id, conn=conn)
        except MediaProviderJobError:
            raise
        except Exception as exc:
            raise MediaProviderJobPersistenceError("media Provider operation failed") from exc

    def get_job(
        self, scope: TenantScope, job_id: str, *, conn: Any | None = None
    ) -> MediaProviderJob:
        def read(connection: Any) -> MediaProviderJob:
            row = connection.execute(
                """SELECT j.*,e.sequence,e.status,e.blocker_codes,e.created_at AS updated_at
                   FROM aip_media_provider_job j
                   JOIN LATERAL (
                     SELECT sequence,status,blocker_codes,created_at
                     FROM aip_media_provider_job_event
                     WHERE org_id=j.org_id AND project_id=j.project_id AND job_id=j.job_id
                     ORDER BY sequence DESC LIMIT 1
                   ) e ON TRUE
                   WHERE j.org_id=%s AND j.project_id=%s AND j.job_id=%s""",
                (*scope.key, job_id),
            ).fetchone()
            if row is None:
                raise MediaProviderJobNotFound(job_id)
            return self._job(scope, row)

        if conn is not None:
            return read(conn)
        with self._connect(scope) as connection:
            return read(connection)

    def list_jobs(self, scope: TenantScope, *, limit: int = 100) -> MediaProviderJobListResponse:
        if not 1 <= limit <= 100:
            raise MediaProviderJobConflict("MEDIA_JOB_LIMIT_INVALID")
        with self._connect(scope) as conn:
            rows = conn.execute(
                """SELECT j.*,e.sequence,e.status,e.blocker_codes,e.created_at AS updated_at
                   FROM aip_media_provider_job j
                   JOIN LATERAL (
                     SELECT sequence,status,blocker_codes,created_at
                     FROM aip_media_provider_job_event
                     WHERE org_id=j.org_id AND project_id=j.project_id AND job_id=j.job_id
                     ORDER BY sequence DESC LIMIT 1
                   ) e ON TRUE
                   WHERE j.org_id=%s AND j.project_id=%s
                   ORDER BY j.created_at DESC,j.job_id LIMIT %s""",
                (*scope.key, limit),
            ).fetchall()
            items = [self._job(scope, row) for row in rows]
            return MediaProviderJobListResponse(
                tenant=self._tenant(scope), items=items, count=len(items)
            )

    def list_events(self, scope: TenantScope, job_id: str) -> list[MediaProviderJobEvent]:
        with self._connect(scope) as conn:
            rows = conn.execute(
                """SELECT * FROM aip_media_provider_job_event
                   WHERE org_id=%s AND project_id=%s AND job_id=%s ORDER BY sequence""",
                (*scope.key, job_id),
            ).fetchall()
            if not rows:
                raise MediaProviderJobNotFound(job_id)
            return [
                MediaProviderJobEvent(
                    tenant=self._tenant(scope), jobId=row["job_id"],
                    sequence=row["sequence"], eventType=row["event_type"],
                    status=row["status"], providerReceiptRef=row["provider_receipt_ref"],
                    blockerCodes=row["blocker_codes"], eventHash=row["event_hash"],
                    actor=row["actor"], createdAt=row["created_at"],
                )
                for row in rows
            ]

    def _job(self, scope: TenantScope, row: Any) -> MediaProviderJob:
        return MediaProviderJob(
            tenant=self._tenant(scope), jobId=row["job_id"],
            taskRunRef=row["task_run_ref"], stepRunRef=row["step_run_ref"],
            binding=row["binding_snapshot"], inputArtifactRefs=row["input_artifact_refs"],
            inputScanRefs=row["input_scan_refs"],
            scanPolicyRef=row["scan_policy_ref"], scannerRef=row["scanner_ref"],
            expectedOutputModality=row["expected_output_modality"],
            purpose=row["purpose"], dataClassification=row["data_classification"],
            requestFingerprint=row["request_fingerprint"], status=row["status"],
            sequence=row["sequence"], blockerCodes=row["blocker_codes"],
            createdBy=row["created_by"], createdAt=row["created_at"],
            updatedAt=row["updated_at"],
        )

    def _latest_event(self, conn: Any, scope: TenantScope, job_id: str, *, lock: bool) -> Any:
        if lock:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{scope.org_id}:{scope.project_id}:{job_id}",),
            )
        return conn.execute(
            """SELECT * FROM aip_media_provider_job_event
               WHERE org_id=%s AND project_id=%s AND job_id=%s
               ORDER BY sequence DESC LIMIT 1""",
            (*scope.key, job_id),
        ).fetchone()

    @staticmethod
    def _event_type(operation: ProviderOperation) -> MediaJobEventType:
        if operation is ProviderOperation.SUBMIT:
            return MediaJobEventType.SUBMITTED
        if operation is ProviderOperation.CANCEL:
            return MediaJobEventType.CANCEL_REQUESTED
        if operation is ProviderOperation.RECONCILE:
            return MediaJobEventType.RECONCILED
        return MediaJobEventType.STATUS_OBSERVED

    @staticmethod
    def _assert_transition(
        current: MediaJobStatus,
        operation: ProviderOperation,
        target: MediaJobStatus,
    ) -> None:
        terminal = {MediaJobStatus.SUCCEEDED, MediaJobStatus.FAILED, MediaJobStatus.CANCELLED}
        if current in terminal:
            raise MediaProviderJobConflict("MEDIA_JOB_TERMINAL")
        allowed: dict[ProviderOperation, dict[MediaJobStatus, set[MediaJobStatus]]] = {
            ProviderOperation.SUBMIT: {
                MediaJobStatus.PREPARED: {
                    MediaJobStatus.SUBMITTED, MediaJobStatus.UNKNOWN, MediaJobStatus.FAILED,
                }
            },
            ProviderOperation.STATUS: {
                MediaJobStatus.SUBMITTED: {
                    MediaJobStatus.RUNNING, MediaJobStatus.SUCCEEDED,
                    MediaJobStatus.FAILED, MediaJobStatus.UNKNOWN,
                },
                MediaJobStatus.RUNNING: {
                    MediaJobStatus.RUNNING, MediaJobStatus.SUCCEEDED,
                    MediaJobStatus.FAILED, MediaJobStatus.UNKNOWN,
                },
                MediaJobStatus.CANCEL_REQUESTED: {
                    MediaJobStatus.CANCELLED, MediaJobStatus.SUCCEEDED,
                    MediaJobStatus.FAILED, MediaJobStatus.UNKNOWN,
                },
            },
            ProviderOperation.WEBHOOK: {
                MediaJobStatus.SUBMITTED: {
                    MediaJobStatus.RUNNING, MediaJobStatus.SUCCEEDED,
                    MediaJobStatus.FAILED, MediaJobStatus.UNKNOWN,
                },
                MediaJobStatus.RUNNING: {
                    MediaJobStatus.RUNNING, MediaJobStatus.SUCCEEDED,
                    MediaJobStatus.FAILED, MediaJobStatus.UNKNOWN,
                },
                MediaJobStatus.CANCEL_REQUESTED: {
                    MediaJobStatus.CANCELLED, MediaJobStatus.SUCCEEDED,
                    MediaJobStatus.FAILED, MediaJobStatus.UNKNOWN,
                },
            },
            ProviderOperation.CANCEL: {
                MediaJobStatus.SUBMITTED: {MediaJobStatus.CANCEL_REQUESTED, MediaJobStatus.UNKNOWN},
                MediaJobStatus.RUNNING: {MediaJobStatus.CANCEL_REQUESTED, MediaJobStatus.UNKNOWN},
                MediaJobStatus.UNKNOWN: {MediaJobStatus.CANCEL_REQUESTED, MediaJobStatus.UNKNOWN},
            },
            ProviderOperation.RECONCILE: {
                MediaJobStatus.UNKNOWN: {
                    MediaJobStatus.UNKNOWN, MediaJobStatus.RUNNING,
                    MediaJobStatus.SUCCEEDED, MediaJobStatus.FAILED, MediaJobStatus.CANCELLED,
                },
                MediaJobStatus.CANCEL_REQUESTED: {
                    MediaJobStatus.UNKNOWN, MediaJobStatus.SUCCEEDED,
                    MediaJobStatus.FAILED, MediaJobStatus.CANCELLED,
                },
            },
        }
        if target not in allowed.get(operation, {}).get(current, set()):
            raise MediaProviderJobConflict(
                f"MEDIA_JOB_TRANSITION_BLOCKED:{current.value}:{operation.value}:{target.value}"
            )

    def _replay(
        self, conn: Any, scope: TenantScope, operation: str, key: str, request_hash: str
    ) -> dict[str, Any] | None:
        row = conn.execute(
            """SELECT request_hash,result_ref FROM aip_media_provider_job_idempotency
               WHERE org_id=%s AND project_id=%s AND operation=%s AND idempotency_key=%s""",
            (*scope.key, operation, key),
        ).fetchone()
        if row is None:
            return None
        if row["request_hash"] != request_hash:
            raise MediaProviderJobConflict("MEDIA_JOB_IDEMPOTENCY_CONFLICT")
        return row["result_ref"]

    def _idempotency(
        self,
        conn: Any,
        scope: TenantScope,
        operation: str,
        key: str,
        request_hash: str,
        result_ref: dict[str, Any],
    ) -> None:
        conn.execute(
            """INSERT INTO aip_media_provider_job_idempotency(
               org_id,project_id,operation,idempotency_key,request_hash,result_ref)
               VALUES(%s,%s,%s,%s,%s,%s::jsonb)""",
            (*scope.key, operation, key, request_hash, self._json(result_ref)),
        )


__all__ = [
    "AipMediaProviderJobStore",
    "MediaProviderJobConflict",
    "MediaProviderJobDependencyBlocked",
    "MediaProviderJobError",
    "MediaProviderJobNotFound",
    "MediaProviderJobPersistenceError",
]

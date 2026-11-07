"""PostgreSQL authority for external ResearchJob adapter facts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import psycopg

from aos_api.aip_contracts import ArtifactRef, ResourceRef, TenantContext
from aos_api.aip_research_job import (
    CancelResearchJobRequest,
    CreateResearchJobRequest,
    ReconcileResearchJobRequest,
    RecordResearchArtifactRequest,
    RecordResearchDeliveryRequest,
    RecordResearchSubmissionRequest,
    RegisterResearchProviderRequest,
    ResearchArtifactReceipt,
    ResearchDeliveryReceipt,
    ResearchJobEvent,
    ResearchJobListResponse,
    ResearchJobObservation,
    ResearchJobSnapshot,
    ResearchJobStatus,
    ResearchProviderRevision,
    ResearchProviderStatus,
    ResearchSubmissionReceipt,
    RetryResearchJobRequest,
    canonical_research_manifest_hash,
)
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


class AipResearchJobError(RuntimeError):
    code = "AIP_RESEARCH_JOB_FAILED"


class AipResearchJobNotFound(AipResearchJobError):
    code = "AIP_RESEARCH_JOB_NOT_FOUND"


class AipResearchJobConflict(AipResearchJobError):
    code = "AIP_RESEARCH_JOB_CONFLICT"


class AipResearchJobBlocked(AipResearchJobError):
    code = "AIP_RESEARCH_JOB_BLOCKED"


class AipResearchJobPersistenceError(AipResearchJobError):
    code = "AIP_RESEARCH_JOB_PERSISTENCE_ERROR"


@dataclass(frozen=True)
class ResearchJobProjectionFacts:
    """Existing append-only facts used only by the unified read projection."""

    partial_refs: list[ResourceRef]
    receipt_refs: list[ResourceRef]
    updated_at: datetime
    deadline: datetime
    owner: str


_ALLOWED = {
    ResearchJobStatus.QUEUED: {
        ResearchJobStatus.QUEUED,
        ResearchJobStatus.RUNNING,
        ResearchJobStatus.UNKNOWN,
    },
    ResearchJobStatus.RUNNING: {
        ResearchJobStatus.RUNNING,
        ResearchJobStatus.SUCCEEDED,
        ResearchJobStatus.FAILED,
        ResearchJobStatus.CANCELLED,
        ResearchJobStatus.UNKNOWN,
    },
    ResearchJobStatus.UNKNOWN: {
        ResearchJobStatus.UNKNOWN,
        ResearchJobStatus.SUCCEEDED,
        ResearchJobStatus.FAILED,
        ResearchJobStatus.CANCELLED,
    },
    ResearchJobStatus.SUCCEEDED: {ResearchJobStatus.SUCCEEDED},
    ResearchJobStatus.FAILED: {ResearchJobStatus.FAILED},
    ResearchJobStatus.CANCELLED: {ResearchJobStatus.CANCELLED},
}


class AipResearchJobStore:
    """Append facts and derive the current ResearchJob observation."""

    def __init__(self, connect_fn=connect) -> None:
        self._connect_fn = connect_fn

    @contextmanager
    def _connect(self, scope: TenantScope) -> Iterator[psycopg.Connection]:
        try:
            with self._connect_fn(scope) as conn:
                yield conn
        except AipResearchJobError:
            raise
        except psycopg.Error as exc:
            raise AipResearchJobPersistenceError(
                "research job persistence failed"
            ) from exc

    def register_provider(
        self,
        scope: TenantScope,
        request: RegisterResearchProviderRequest,
        actor: str,
        created_at: datetime,
    ) -> ResearchProviderRevision:
        source_hash = _hash(request.model_dump(mode="json", by_alias=True))
        with self._connect(scope) as conn:
            existing = conn.execute(
                """SELECT * FROM aip_research_provider_revision
                   WHERE org_id=%s AND project_id=%s AND provider_id=%s AND revision=%s""",
                (scope.org_id, scope.project_id, request.provider_id, request.revision),
            ).fetchone()
            if existing:
                if existing["source_hash"] != source_hash:
                    raise AipResearchJobConflict("provider revision payload drifted")
                return self._provider(scope, existing)
            latest = conn.execute(
                """SELECT COALESCE(MAX(revision),0) AS revision
                   FROM aip_research_provider_revision
                   WHERE org_id=%s AND project_id=%s AND provider_id=%s""",
                (scope.org_id, scope.project_id, request.provider_id),
            ).fetchone()["revision"]
            if request.revision != int(latest) + 1:
                raise AipResearchJobConflict("provider revision must be contiguous")
            capability = request.capability_ref
            conn.execute(
                """INSERT INTO aip_research_provider_revision (
                     org_id,project_id,provider_id,revision,adapter_kind,
                     capability_type,capability_id,capability_revision,capability_authority,
                     contract_hash,callback_secret_ref_hash,status,source_hash,created_by,created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    scope.org_id,
                    scope.project_id,
                    request.provider_id,
                    request.revision,
                    request.adapter_kind,
                    capability.resource_type,
                    capability.resource_id,
                    capability.revision,
                    capability.authority,
                    request.contract_hash,
                    request.callback_secret_ref_hash,
                    request.status.value,
                    source_hash,
                    actor,
                    created_at,
                ),
            )
            conn.commit()
            row = conn.execute(
                """SELECT * FROM aip_research_provider_revision
                   WHERE org_id=%s AND project_id=%s AND provider_id=%s AND revision=%s""",
                (scope.org_id, scope.project_id, request.provider_id, request.revision),
            ).fetchone()
            return self._provider(scope, row)

    def create_job(
        self,
        scope: TenantScope,
        request: CreateResearchJobRequest,
        actor: str,
        created_at: datetime,
    ) -> ResearchJobSnapshot:
        manifest = request.manifest
        calculated_hash = canonical_research_manifest_hash(manifest)
        if manifest.manifest_hash != calculated_hash:
            raise AipResearchJobBlocked("research manifest hash mismatch")
        if manifest.provider != request.provider_id:
            raise AipResearchJobBlocked("manifest provider does not match request")
        if manifest.binding_revision != str(request.provider_revision):
            raise AipResearchJobBlocked("manifest provider revision drifted")
        if manifest.task_run_ref.resource_id != request.run_id:
            raise AipResearchJobBlocked("manifest task run does not match request")
        request_hash = _hash(request.model_dump(mode="json", by_alias=True))
        job_id = _id("research-job", scope, manifest.idempotency_key)
        with self._connect(scope) as conn:
            existing = conn.execute(
                """SELECT * FROM aip_research_job_manifest
                   WHERE org_id=%s AND project_id=%s AND idempotency_key=%s""",
                (scope.org_id, scope.project_id, manifest.idempotency_key),
            ).fetchone()
            if existing:
                if existing["request_hash"] != request_hash:
                    raise AipResearchJobConflict(
                        "research job idempotency payload drifted"
                    )
                return self._snapshot(conn, scope, existing)
            provider = self._current_provider(
                conn, scope, request.provider_id, request.provider_revision
            )
            if provider["status"] != ResearchProviderStatus.ENABLED.value:
                raise AipResearchJobBlocked("research provider is disabled")
            run = conn.execute(
                """SELECT * FROM aip_task_run
                   WHERE org_id=%s AND project_id=%s AND run_id=%s""",
                (scope.org_id, scope.project_id, request.run_id),
            ).fetchone()
            if run is None:
                raise AipResearchJobNotFound("task run not found in scope")
            if manifest.task_run_ref.resource_type != "aos.task_run":
                raise AipResearchJobBlocked("manifest requires aos.task_run authority")
            if manifest.task_run_ref.revision != str(run["version"]):
                raise AipResearchJobBlocked("manifest task run revision drifted")
            lineage_sequence = int(manifest.lineage_ref.revision or "0")
            lineage = conn.execute(
                """SELECT * FROM aip_lineage_event
                   WHERE org_id=%s AND project_id=%s AND lineage_id=%s AND sequence=%s""",
                (
                    scope.org_id,
                    scope.project_id,
                    manifest.lineage_ref.resource_id,
                    lineage_sequence,
                ),
            ).fetchone()
            if lineage is None:
                raise AipResearchJobNotFound("exact lineage event not found in scope")
            latest_sequence = conn.execute(
                """SELECT MAX(sequence) AS sequence FROM aip_lineage_event
                   WHERE org_id=%s AND project_id=%s AND lineage_id=%s""",
                (
                    scope.org_id,
                    scope.project_id,
                    manifest.lineage_ref.resource_id,
                ),
            ).fetchone()["sequence"]
            if lineage_sequence != int(latest_sequence):
                raise AipResearchJobBlocked("research job requires latest lineage sequence")
            if lineage["root_type"] != "task_run" or lineage["root_id"] != request.run_id:
                raise AipResearchJobBlocked("research lineage does not belong to task run")
            plan = conn.execute(
                """SELECT * FROM aip_plan_revision
                   WHERE org_id=%s AND project_id=%s AND plan_revision_id=%s""",
                (scope.org_id, scope.project_id, run["plan_revision_id"]),
            ).fetchone()
            if plan is None or plan["approval_status"] != "approved":
                raise AipResearchJobBlocked("research job requires an approved plan")
            step = next(
                (
                    item
                    for item in plan["steps"]
                    if item.get("stepKey") == request.step_key
                ),
                None,
            )
            if step is None or step.get("capabilityRef") is None:
                raise AipResearchJobBlocked("research step has no capability binding")
            expected = {
                "resourceType": provider["capability_type"],
                "resourceId": provider["capability_id"],
                "revision": provider["capability_revision"],
                "authority": provider["capability_authority"],
            }
            if step["capabilityRef"] != expected:
                raise AipResearchJobBlocked("research capability binding drifted")
            conn.execute(
                """INSERT INTO aip_research_job_manifest (
                     org_id,project_id,job_id,run_id,plan_revision_id,step_key,
                     provider_id,provider_revision,capability_type,capability_id,
                     capability_revision,capability_authority,manifest_hash,output_schema_hash,
                     lineage_id,lineage_sequence,lineage_event_id,
                     idempotency_key,request_hash,manifest,created_by,created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)""",
                (
                    scope.org_id,
                    scope.project_id,
                    job_id,
                    request.run_id,
                    run["plan_revision_id"],
                    request.step_key,
                    request.provider_id,
                    request.provider_revision,
                    provider["capability_type"],
                    provider["capability_id"],
                    provider["capability_revision"],
                    provider["capability_authority"],
                    manifest.manifest_hash,
                    manifest.output_schema_hash,
                    lineage["lineage_id"],
                    lineage["sequence"],
                    lineage["event_id"],
                    manifest.idempotency_key,
                    request_hash,
                    _json(manifest.model_dump(mode="json", by_alias=True)),
                    actor,
                    created_at,
                ),
            )
            conn.commit()
            row = conn.execute(
                """SELECT * FROM aip_research_job_manifest
                   WHERE org_id=%s AND project_id=%s AND job_id=%s""",
                (scope.org_id, scope.project_id, job_id),
            ).fetchone()
            return self._snapshot(conn, scope, row)

    def record_submission(
        self,
        scope: TenantScope,
        request: RecordResearchSubmissionRequest,
        created_at: datetime,
    ) -> ResearchSubmissionReceipt:
        receipt_id = _id("research-submission", scope, request.job_id)
        with self._connect(scope) as conn:
            job = self._job(conn, scope, request.job_id)
            existing = conn.execute(
                """SELECT * FROM aip_research_submission_receipt
                   WHERE org_id=%s AND project_id=%s AND job_id=%s""",
                (scope.org_id, scope.project_id, request.job_id),
            ).fetchone()
            if existing:
                if self._submission_payload(existing) != request.model_dump(
                    mode="json", by_alias=True
                ):
                    raise AipResearchJobConflict("submission receipt payload drifted")
                return self._submission(scope, existing)
            if request.accepted_manifest_hash != job["manifest_hash"]:
                raise AipResearchJobBlocked(
                    "provider accepted a different manifest hash"
                )
            if request.provider_version != str(job["provider_revision"]):
                raise AipResearchJobBlocked("provider submission revision drifted")
            conn.execute(
                """INSERT INTO aip_research_submission_receipt (
                     org_id,project_id,submission_receipt_id,job_id,provider_execution_id,
                     provider_version,accepted_manifest_hash,source_hash,observed_at,created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    scope.org_id,
                    scope.project_id,
                    receipt_id,
                    request.job_id,
                    request.provider_execution_id,
                    request.provider_version,
                    request.accepted_manifest_hash,
                    request.source_hash,
                    request.observed_at,
                    created_at,
                ),
            )
            conn.commit()
            row = conn.execute(
                """SELECT * FROM aip_research_submission_receipt
                   WHERE org_id=%s AND project_id=%s AND submission_receipt_id=%s""",
                (scope.org_id, scope.project_id, receipt_id),
            ).fetchone()
            return self._submission(scope, row)

    def record_event(
        self,
        scope: TenantScope,
        job_id: str,
        event: ResearchJobEvent,
        created_at: datetime,
    ) -> ResearchJobSnapshot:
        receipt_id = _id(
            "research-event", scope, event.provider_execution_id, event.event_id
        )
        with self._connect(scope) as conn:
            job = self._job(conn, scope, job_id)
            submission = self._submission_row(conn, scope, job_id)
            if submission["provider_execution_id"] != event.provider_execution_id:
                raise AipResearchJobBlocked("provider execution id drifted")
            existing = conn.execute(
                """SELECT * FROM aip_research_event_receipt
                   WHERE org_id=%s AND project_id=%s AND provider_execution_id=%s
                     AND (sequence=%s OR provider_event_id=%s)""",
                (
                    scope.org_id,
                    scope.project_id,
                    event.provider_execution_id,
                    event.sequence,
                    event.event_id,
                ),
            ).fetchone()
            if existing:
                expected = (
                    event.sequence,
                    event.event_id,
                    event.status.value,
                    event.payload_hash,
                )
                actual = (
                    existing["sequence"],
                    existing["provider_event_id"],
                    existing["status"],
                    existing["payload_hash"],
                )
                if actual != expected:
                    raise AipResearchJobConflict("provider event replay drifted")
                return self._snapshot(conn, scope, job)
            candidate = {
                "sequence": event.sequence,
                "provider_event_id": event.event_id,
                "status": event.status.value,
            }
            rows = self._event_rows(conn, scope, job_id) + [candidate]
            self._derive_observation(event.provider_execution_id, rows)
            conn.execute(
                """INSERT INTO aip_research_event_receipt (
                     org_id,project_id,event_receipt_id,job_id,provider_execution_id,
                     sequence,provider_event_id,status,payload_hash,observed_at,created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    scope.org_id,
                    scope.project_id,
                    receipt_id,
                    job_id,
                    event.provider_execution_id,
                    event.sequence,
                    event.event_id,
                    event.status.value,
                    event.payload_hash,
                    event.observed_at,
                    created_at,
                ),
            )
            conn.commit()
            return self._snapshot(conn, scope, job)

    def record_callback_nonce(
        self,
        scope: TenantScope,
        provider_id: str,
        provider_revision: int,
        nonce_hash: str,
        body_hash: str,
        callback_timestamp: int,
        observed_at: datetime,
        created_at: datetime,
    ) -> str:
        receipt_id = _id("research-callback", scope, provider_id, nonce_hash)
        with self._connect(scope) as conn:
            provider = self._current_provider(
                conn, scope, provider_id, provider_revision
            )
            if provider["status"] != ResearchProviderStatus.ENABLED.value:
                raise AipResearchJobBlocked("research provider is disabled")
            existing = conn.execute(
                """SELECT * FROM aip_research_callback_nonce
                   WHERE org_id=%s AND project_id=%s AND provider_id=%s AND nonce_hash=%s""",
                (scope.org_id, scope.project_id, provider_id, nonce_hash),
            ).fetchone()
            if existing:
                raise AipResearchJobConflict("research callback nonce was replayed")
            conn.execute(
                """INSERT INTO aip_research_callback_nonce (
                     org_id,project_id,callback_receipt_id,provider_id,provider_revision,
                     nonce_hash,body_hash,callback_timestamp,observed_at,created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    scope.org_id,
                    scope.project_id,
                    receipt_id,
                    provider_id,
                    provider_revision,
                    nonce_hash,
                    body_hash,
                    callback_timestamp,
                    observed_at,
                    created_at,
                ),
            )
            conn.commit()
        return receipt_id

    def record_artifact(
        self,
        scope: TenantScope,
        request: RecordResearchArtifactRequest,
        actor: str,
        created_at: datetime,
    ) -> ResearchArtifactReceipt:
        artifact_id = _id(
            "research-artifact", scope, request.job_id, request.content_ref
        )
        receipt_id = _id("research-artifact-receipt", scope, artifact_id)
        with self._connect(scope) as conn:
            job = self._job(conn, scope, request.job_id)
            submission = self._submission_row(conn, scope, request.job_id)
            if submission["provider_execution_id"] != request.provider_execution_id:
                raise AipResearchJobBlocked("artifact provider execution id drifted")
            existing = conn.execute(
                """SELECT r.*,a.artifact_type,a.schema_ref
                   FROM aip_research_artifact_receipt r
                   JOIN aip_artifact a USING (org_id,project_id,artifact_id)
                   WHERE r.org_id=%s AND r.project_id=%s AND r.job_id=%s AND r.content_ref=%s""",
                (scope.org_id, scope.project_id, request.job_id, request.content_ref),
            ).fetchone()
            if existing:
                if self._artifact_payload(existing) != request.model_dump(
                    mode="json", by_alias=True
                ):
                    raise AipResearchJobConflict("artifact receipt payload drifted")
                return self._artifact(scope, existing)
            conn.execute(
                """INSERT INTO aip_artifact (
                     org_id,project_id,artifact_id,run_id,artifact_type,content_ref,schema_ref,
                     source,evidence_refs,marking,content_hash,metadata,created_by,created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,'[]'::jsonb,'[]'::jsonb,%s,%s::jsonb,%s,%s)""",
                (
                    scope.org_id,
                    scope.project_id,
                    artifact_id,
                    job["run_id"],
                    request.artifact_type,
                    request.content_ref,
                    request.schema_ref,
                    _json(
                        {
                            "kind": "research_provider",
                            "providerId": job["provider_id"],
                            "providerRevision": job["provider_revision"],
                            "providerExecutionId": request.provider_execution_id,
                        }
                    ),
                    request.content_hash,
                    _json({"mediaType": request.media_type}),
                    actor,
                    created_at,
                ),
            )
            conn.execute(
                """INSERT INTO aip_research_artifact_receipt (
                     org_id,project_id,artifact_receipt_id,artifact_id,job_id,
                     provider_execution_id,content_ref,media_type,content_hash,source_hash,
                     observed_at,created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    scope.org_id,
                    scope.project_id,
                    receipt_id,
                    artifact_id,
                    request.job_id,
                    request.provider_execution_id,
                    request.content_ref,
                    request.media_type,
                    request.content_hash,
                    request.source_hash,
                    request.observed_at,
                    created_at,
                ),
            )
            conn.commit()
            row = conn.execute(
                """SELECT r.*,a.artifact_type,a.schema_ref
                   FROM aip_research_artifact_receipt r
                   JOIN aip_artifact a USING (org_id,project_id,artifact_id)
                   WHERE r.org_id=%s AND r.project_id=%s AND r.artifact_receipt_id=%s""",
                (scope.org_id, scope.project_id, receipt_id),
            ).fetchone()
            return self._artifact(scope, row)

    def record_delivery(
        self,
        scope: TenantScope,
        request: RecordResearchDeliveryRequest,
        created_at: datetime,
    ) -> ResearchDeliveryReceipt:
        with self._connect(scope) as conn:
            job = self._job(conn, scope, request.job_id)
            observation = self._observation(conn, scope, job)
            if observation.provider_execution_id != request.provider_execution_id:
                raise AipResearchJobBlocked("delivery provider execution id drifted")
            if request.status.value == "succeeded":
                if (
                    observation.status is not ResearchJobStatus.SUCCEEDED
                    or observation.has_gap
                ):
                    raise AipResearchJobBlocked(
                        "delivery requires gap-free provider succeeded observation"
                    )
                self._validate_current_binding(conn, scope, job)
                self._validate_artifacts(conn, scope, job, request.artifact_ids)
            return self._append_delivery(
                conn,
                scope,
                job,
                request.provider_execution_id,
                "delivery",
                request.status.value,
                request.artifact_ids,
                None,
                request.source_hash,
                request.observed_at,
                created_at,
            )

    def reconcile(
        self,
        scope: TenantScope,
        request: ReconcileResearchJobRequest,
        created_at: datetime,
    ) -> ResearchDeliveryReceipt:
        with self._connect(scope) as conn:
            job = self._job(conn, scope, request.job_id)
            observation = self._observation(conn, scope, job)
            if (
                observation.status is not ResearchJobStatus.UNKNOWN
                and not observation.has_gap
            ):
                raise AipResearchJobBlocked(
                    "reconcile requires unknown status or an event gap"
                )
            submission = self._submission_row(conn, scope, request.job_id)
            reconciled_artifact_ids: list[str] = []
            if request.final_status is ResearchJobStatus.SUCCEEDED:
                artifact_rows = conn.execute(
                    """SELECT artifact_id FROM aip_research_artifact_receipt
                       WHERE org_id=%s AND project_id=%s AND job_id=%s""",
                    (scope.org_id, scope.project_id, request.job_id),
                ).fetchall()
                reconciled_artifact_ids = [
                    str(row["artifact_id"]) for row in artifact_rows
                ]
                self._validate_current_binding(conn, scope, job)
                self._validate_artifacts(
                    conn,
                    scope,
                    job,
                    reconciled_artifact_ids,
                )
            return self._append_delivery(
                conn,
                scope,
                job,
                submission["provider_execution_id"],
                "reconcile",
                request.final_status.value,
                reconciled_artifact_ids,
                request.reason_code,
                request.source_hash,
                request.observed_at,
                created_at,
            )

    def get_job(self, scope: TenantScope, job_id: str) -> ResearchJobSnapshot:
        with self._connect(scope) as conn:
            return self._snapshot(conn, scope, self._job(conn, scope, job_id))

    def list_jobs(
        self, scope: TenantScope, *, limit: int = 50
    ) -> ResearchJobListResponse:
        limit = max(1, min(int(limit), 200))
        with self._connect(scope) as conn:
            rows = conn.execute(
                """SELECT * FROM aip_research_job_manifest
                   WHERE org_id=%s AND project_id=%s
                   ORDER BY created_at DESC, job_id DESC
                   LIMIT %s""",
                (scope.org_id, scope.project_id, limit),
            ).fetchall()
            items = [self._snapshot(conn, scope, row) for row in rows]
            return ResearchJobListResponse(
                tenant=_tenant(scope), items=items, count=len(items)
            )

    def projection_facts(
        self, scope: TenantScope, job_id: str
    ) -> ResearchJobProjectionFacts:
        """Read existing receipts without creating a fourth async-job authority."""
        with self._connect(scope) as conn:
            job = self._job(conn, scope, job_id)
            artifacts = conn.execute(
                """SELECT r.artifact_id,r.content_hash,r.created_at
                   FROM aip_research_artifact_receipt r
                   WHERE r.org_id=%s AND r.project_id=%s AND r.job_id=%s
                   ORDER BY r.created_at,r.artifact_receipt_id""",
                (*scope.key, job_id),
            ).fetchall()
            receipts = conn.execute(
                """SELECT resource_type,resource_id,revision,created_at FROM (
                     SELECT 'aip.research_submission_receipt'::text AS resource_type,
                            submission_receipt_id AS resource_id,source_hash AS revision,created_at
                     FROM aip_research_submission_receipt
                     WHERE org_id=%s AND project_id=%s AND job_id=%s
                     UNION ALL
                     SELECT 'aip.research_event_receipt',event_receipt_id,payload_hash,created_at
                     FROM aip_research_event_receipt
                     WHERE org_id=%s AND project_id=%s AND job_id=%s
                     UNION ALL
                     SELECT 'aip.research_artifact_receipt',artifact_receipt_id,source_hash,created_at
                     FROM aip_research_artifact_receipt
                     WHERE org_id=%s AND project_id=%s AND job_id=%s
                     UNION ALL
                     SELECT 'aip.research_delivery_receipt',receipt_id,source_hash,created_at
                     FROM aip_research_delivery_receipt
                     WHERE org_id=%s AND project_id=%s AND job_id=%s
                     UNION ALL
                     SELECT 'aip.research_command_receipt',receipt_id,request_hash,created_at
                     FROM aip_research_job_command_receipt
                     WHERE org_id=%s AND project_id=%s AND job_id=%s
                   ) facts ORDER BY created_at,resource_type,resource_id""",
                (*scope.key, job_id) * 5,
            ).fetchall()
            updated_at = max(
                [job["created_at"], *[row["created_at"] for row in receipts]],
            )
            manifest = job["manifest"]
            if isinstance(manifest, str):
                manifest = json.loads(manifest)
            return ResearchJobProjectionFacts(
                partial_refs=[
                    ResourceRef(
                        resource_type="aip.artifact",
                        resource_id=row["artifact_id"],
                        revision=row["content_hash"],
                        authority="aos.artifact",
                    )
                    for row in artifacts
                ],
                receipt_refs=[
                    ResourceRef(
                        resource_type=row["resource_type"],
                        resource_id=row["resource_id"],
                        revision=row["revision"],
                        authority="aos.research_job",
                    )
                    for row in receipts
                ],
                updated_at=updated_at,
                deadline=datetime.fromisoformat(
                    str(manifest["deadline"]).replace("Z", "+00:00")
                ),
                owner=job["created_by"],
            )

    def cancel_job(
        self,
        scope: TenantScope,
        job_id: str,
        request: CancelResearchJobRequest,
        actor: str,
        idempotency_key: str,
        *,
        now: datetime,
    ) -> ResearchJobSnapshot:
        request_hash = _hash(
            {
                "jobId": job_id,
                "reason": request.reason,
                "actor": actor,
                "command": "cancel",
            }
        )
        with self._connect(scope) as conn:
            job = self._job(conn, scope, job_id)
            replay = conn.execute(
                """SELECT request_hash, outcome_status FROM aip_research_job_command_receipt
                   WHERE org_id=%s AND project_id=%s AND command='cancel'
                     AND idempotency_key=%s""",
                (scope.org_id, scope.project_id, idempotency_key),
            ).fetchone()
            if replay is not None:
                if replay["request_hash"] != request_hash:
                    raise AipResearchJobConflict(
                        "cancel idempotency key reused with different payload"
                    )
                return self._snapshot(conn, scope, job)
            snapshot = self._snapshot(conn, scope, job)
            if snapshot.status in {
                ResearchJobStatus.SUCCEEDED,
                ResearchJobStatus.FAILED,
                ResearchJobStatus.CANCELLED,
            }:
                raise AipResearchJobBlocked(
                    f"research job already terminal ({snapshot.status.value})"
                )
            outcome = (
                ResearchJobStatus.CANCELLED.value
                if snapshot.provider_execution_id is None
                else ResearchJobStatus.UNKNOWN.value
            )
            conn.execute(
                """INSERT INTO aip_research_job_command_receipt
                   (org_id,project_id,receipt_id,job_id,command,idempotency_key,
                    request_hash,actor,outcome_status,created_at)
                   VALUES(%s,%s,%s,%s,'cancel',%s,%s,%s,%s,%s)""",
                (
                    scope.org_id,
                    scope.project_id,
                    _id("research-cmd", scope, job_id, idempotency_key),
                    job_id,
                    idempotency_key,
                    request_hash,
                    actor,
                    outcome,
                    now,
                ),
            )
            conn.commit()
            return self._snapshot(conn, scope, self._job(conn, scope, job_id))

    def retry_job(
        self,
        scope: TenantScope,
        job_id: str,
        request: RetryResearchJobRequest,
        actor: str,
        *,
        now: datetime,
    ) -> ResearchJobSnapshot:
        """Provider resume is unsupported; mint a new job linked by retryOf."""
        request_hash = _hash(
            {
                "jobId": job_id,
                "reason": request.reason,
                "actor": actor,
                "command": "retry",
                "idempotencyKey": request.idempotency_key,
            }
        )
        with self._connect(scope) as conn:
            source = self._job(conn, scope, job_id)
            replay = conn.execute(
                """SELECT request_hash, retry_job_id FROM aip_research_job_command_receipt
                   WHERE org_id=%s AND project_id=%s AND command='retry'
                     AND idempotency_key=%s""",
                (scope.org_id, scope.project_id, request.idempotency_key),
            ).fetchone()
            if replay is not None:
                if replay["request_hash"] != request_hash:
                    raise AipResearchJobConflict(
                        "retry idempotency key reused with different payload"
                    )
                if not replay["retry_job_id"]:
                    raise AipResearchJobConflict("retry receipt missing retry job")
                return self._snapshot(
                    conn, scope, self._job(conn, scope, replay["retry_job_id"])
                )
            from aos_api.aip_research_job import ResearchJobManifest

            raw_manifest = source["manifest"]
            if isinstance(raw_manifest, str):
                import json as _json_mod

                raw_manifest = _json_mod.loads(raw_manifest)
            manifest_model = ResearchJobManifest.model_validate(raw_manifest)
            reminted = manifest_model.model_copy(
                update={"idempotency_key": request.idempotency_key}
            )
            reminted = reminted.model_copy(
                update={"manifest_hash": canonical_research_manifest_hash(reminted)}
            )
            create_req = CreateResearchJobRequest(
                run_id=source["run_id"],
                step_key=source["step_key"],
                provider_id=source["provider_id"],
                provider_revision=int(source["provider_revision"]),
                manifest=reminted,
            )
        created = self.create_job(scope, create_req, actor, now)
        with self._connect(scope) as conn:
            conn.execute(
                """INSERT INTO aip_research_job_command_receipt
                   (org_id,project_id,receipt_id,job_id,command,idempotency_key,
                    request_hash,actor,outcome_status,retry_job_id,created_at)
                   VALUES(%s,%s,%s,%s,'retry',%s,%s,%s,%s,%s,%s)""",
                (
                    scope.org_id,
                    scope.project_id,
                    _id("research-cmd", scope, job_id, request.idempotency_key),
                    job_id,
                    request.idempotency_key,
                    request_hash,
                    actor,
                    created.status.value,
                    created.job_id,
                    now,
                ),
            )
            conn.commit()
        # Attach retryOf on the new snapshot view via command lookup
        with self._connect(scope) as conn:
            snap = self._snapshot(conn, scope, self._job(conn, scope, created.job_id))
            return snap.model_copy(update={"retry_of_job_id": job_id})

    def get_current_provider(
        self, scope: TenantScope, provider_id: str, revision: int
    ) -> ResearchProviderRevision:
        with self._connect(scope) as conn:
            return self._provider(
                scope, self._current_provider(conn, scope, provider_id, revision)
            )

    def _snapshot(
        self, conn: psycopg.Connection, scope: TenantScope, job: Any
    ) -> ResearchJobSnapshot:
        observation = self._observation(conn, scope, job)
        latest_reconcile = conn.execute(
            """SELECT status FROM aip_research_delivery_receipt
               WHERE org_id=%s AND project_id=%s AND job_id=%s AND receipt_kind='reconcile'
               ORDER BY created_at DESC,receipt_id DESC LIMIT 1""",
            (scope.org_id, scope.project_id, job["job_id"]),
        ).fetchone()
        status = (
            ResearchJobStatus(latest_reconcile["status"])
            if latest_reconcile
            else observation.status
        )
        cancel = conn.execute(
            """SELECT outcome_status FROM aip_research_job_command_receipt
               WHERE org_id=%s AND project_id=%s AND job_id=%s AND command='cancel'
               ORDER BY created_at DESC, receipt_id DESC LIMIT 1""",
            (scope.org_id, scope.project_id, job["job_id"]),
        ).fetchone()
        cancel_requested = cancel is not None
        if cancel is not None and status not in {
            ResearchJobStatus.SUCCEEDED,
            ResearchJobStatus.FAILED,
            ResearchJobStatus.CANCELLED,
        }:
            status = ResearchJobStatus(cancel["outcome_status"] or "unknown")
        retry_of = conn.execute(
            """SELECT job_id FROM aip_research_job_command_receipt
               WHERE org_id=%s AND project_id=%s AND command='retry'
                 AND retry_job_id=%s
               ORDER BY created_at DESC LIMIT 1""",
            (scope.org_id, scope.project_id, job["job_id"]),
        ).fetchone()
        return ResearchJobSnapshot(
            tenant=_tenant(scope),
            job_id=job["job_id"],
            run_id=job["run_id"],
            plan_revision_id=job["plan_revision_id"],
            step_key=job["step_key"],
            provider_id=job["provider_id"],
            provider_revision=job["provider_revision"],
            capability_ref=ResourceRef(
                resource_type=job["capability_type"],
                resource_id=job["capability_id"],
                revision=job["capability_revision"],
                authority=job["capability_authority"],
            ),
            lineage_ref=ResourceRef(
                resource_type="aip.lineage",
                resource_id=job["lineage_id"],
                revision=str(job["lineage_sequence"]),
                authority="aos.lineage",
            ),
            manifest_hash=job["manifest_hash"],
            output_schema_hash=job["output_schema_hash"],
            status=status,
            provider_execution_id=(
                None
                if observation.provider_execution_id == "unsubmitted"
                else observation.provider_execution_id
            ),
            last_sequence=observation.last_sequence,
            has_gap=observation.has_gap,
            created_at=job["created_at"],
            cancel_requested=cancel_requested,
            resumability="unsupported",
            retry_of_job_id=None if retry_of is None else retry_of["job_id"],
        )

    def _observation(
        self, conn: psycopg.Connection, scope: TenantScope, job: Any
    ) -> ResearchJobObservation:
        submission = conn.execute(
            """SELECT * FROM aip_research_submission_receipt
               WHERE org_id=%s AND project_id=%s AND job_id=%s""",
            (scope.org_id, scope.project_id, job["job_id"]),
        ).fetchone()
        if submission is None:
            return ResearchJobObservation(
                provider_execution_id="unsubmitted",
                status=ResearchJobStatus.QUEUED,
                last_sequence=0,
            )
        return self._derive_observation(
            submission["provider_execution_id"],
            self._event_rows(conn, scope, job["job_id"]),
        )

    @staticmethod
    def _derive_observation(
        provider_execution_id: str, rows: list[Any]
    ) -> ResearchJobObservation:
        ordered = sorted(
            rows, key=lambda row: (int(row["sequence"]), row["provider_event_id"])
        )
        status = ResearchJobStatus.QUEUED
        sequence = 0
        event_ids: list[str] = []
        has_gap = False
        for row in ordered:
            current_sequence = int(row["sequence"])
            if current_sequence <= sequence:
                continue
            if current_sequence != sequence + 1:
                has_gap = True
                break
            candidate = ResearchJobStatus(row["status"])
            if candidate not in _ALLOWED[status]:
                raise AipResearchJobBlocked(
                    f"research status cannot regress from {status} to {candidate}"
                )
            status = candidate
            sequence = current_sequence
            event_ids.append(str(row["provider_event_id"]))
        return ResearchJobObservation(
            provider_execution_id=provider_execution_id,
            status=status,
            last_sequence=sequence,
            event_ids=event_ids,
            has_gap=has_gap,
        )

    def _validate_current_binding(
        self, conn: psycopg.Connection, scope: TenantScope, job: Any
    ) -> None:
        provider = self._current_provider(
            conn, scope, job["provider_id"], int(job["provider_revision"])
        )
        if provider["status"] != ResearchProviderStatus.ENABLED.value:
            raise AipResearchJobBlocked("research provider is disabled")
        plan = conn.execute(
            """SELECT approval_status,steps FROM aip_plan_revision
               WHERE org_id=%s AND project_id=%s AND plan_revision_id=%s""",
            (scope.org_id, scope.project_id, job["plan_revision_id"]),
        ).fetchone()
        if plan is None or plan["approval_status"] != "approved":
            raise AipResearchJobBlocked("research plan is no longer approved")
        step = next(
            (item for item in plan["steps"] if item.get("stepKey") == job["step_key"]),
            None,
        )
        expected = {
            "resourceType": job["capability_type"],
            "resourceId": job["capability_id"],
            "revision": job["capability_revision"],
            "authority": job["capability_authority"],
        }
        if step is None or step.get("capabilityRef") != expected:
            raise AipResearchJobBlocked("research capability binding drifted")

    def _validate_artifacts(
        self,
        conn: psycopg.Connection,
        scope: TenantScope,
        job: Any,
        artifact_ids: list[str],
    ) -> None:
        if not artifact_ids:
            raise AipResearchJobBlocked("verified research artifacts are required")
        rows = conn.execute(
            """SELECT r.artifact_id,r.content_hash AS receipt_hash,a.content_hash AS artifact_hash
               FROM aip_research_artifact_receipt r
               JOIN aip_artifact a USING (org_id,project_id,artifact_id)
               WHERE r.org_id=%s AND r.project_id=%s AND r.job_id=%s
                 AND r.artifact_id=ANY(%s)""",
            (scope.org_id, scope.project_id, job["job_id"], artifact_ids),
        ).fetchall()
        if len(rows) != len(set(artifact_ids)):
            raise AipResearchJobBlocked("delivery references unverified artifacts")
        if any(row["receipt_hash"] != row["artifact_hash"] for row in rows):
            raise AipResearchJobBlocked("research artifact hash drifted")

    def _append_delivery(
        self,
        conn: psycopg.Connection,
        scope: TenantScope,
        job: Any,
        provider_execution_id: str,
        receipt_kind: str,
        status: str,
        artifact_ids: list[str],
        reason_code: str | None,
        source_hash: str,
        observed_at: datetime,
        created_at: datetime,
    ) -> ResearchDeliveryReceipt:
        receipt_id = _id(
            "research-receipt", scope, job["job_id"], receipt_kind, source_hash
        )
        existing = conn.execute(
            """SELECT * FROM aip_research_delivery_receipt
               WHERE org_id=%s AND project_id=%s AND receipt_id=%s""",
            (scope.org_id, scope.project_id, receipt_id),
        ).fetchone()
        if existing:
            expected = {
                "jobId": job["job_id"],
                "providerExecutionId": provider_execution_id,
                "receiptKind": receipt_kind,
                "status": status,
                "artifactIds": artifact_ids,
                "reasonCode": reason_code,
                "sourceHash": source_hash,
                "observedAt": observed_at.isoformat().replace("+00:00", "Z"),
            }
            if self._delivery_payload(existing) != expected:
                raise AipResearchJobConflict("delivery receipt payload drifted")
            return self._delivery(scope, existing)
        conn.execute(
            """INSERT INTO aip_research_delivery_receipt (
                 org_id,project_id,receipt_id,job_id,provider_execution_id,receipt_kind,
                 status,artifact_ids,reason_code,source_hash,observed_at,created_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)""",
            (
                scope.org_id,
                scope.project_id,
                receipt_id,
                job["job_id"],
                provider_execution_id,
                receipt_kind,
                status,
                _json(artifact_ids),
                reason_code,
                source_hash,
                observed_at,
                created_at,
            ),
        )
        conn.commit()
        row = conn.execute(
            """SELECT * FROM aip_research_delivery_receipt
               WHERE org_id=%s AND project_id=%s AND receipt_id=%s""",
            (scope.org_id, scope.project_id, receipt_id),
        ).fetchone()
        return self._delivery(scope, row)

    @staticmethod
    def _event_rows(
        conn: psycopg.Connection, scope: TenantScope, job_id: str
    ) -> list[Any]:
        return list(
            conn.execute(
                """SELECT * FROM aip_research_event_receipt
                   WHERE org_id=%s AND project_id=%s AND job_id=%s
                   ORDER BY sequence,provider_event_id""",
                (scope.org_id, scope.project_id, job_id),
            ).fetchall()
        )

    @staticmethod
    def _job(conn: psycopg.Connection, scope: TenantScope, job_id: str) -> Any:
        row = conn.execute(
            """SELECT * FROM aip_research_job_manifest
               WHERE org_id=%s AND project_id=%s AND job_id=%s""",
            (scope.org_id, scope.project_id, job_id),
        ).fetchone()
        if row is None:
            raise AipResearchJobNotFound("research job not found in scope")
        return row

    @staticmethod
    def _submission_row(
        conn: psycopg.Connection, scope: TenantScope, job_id: str
    ) -> Any:
        row = conn.execute(
            """SELECT * FROM aip_research_submission_receipt
               WHERE org_id=%s AND project_id=%s AND job_id=%s""",
            (scope.org_id, scope.project_id, job_id),
        ).fetchone()
        if row is None:
            raise AipResearchJobBlocked("research job has no submission receipt")
        return row

    @staticmethod
    def _current_provider(
        conn: psycopg.Connection,
        scope: TenantScope,
        provider_id: str,
        revision: int,
    ) -> Any:
        latest = conn.execute(
            """SELECT * FROM aip_research_provider_revision
               WHERE org_id=%s AND project_id=%s AND provider_id=%s
               ORDER BY revision DESC LIMIT 1""",
            (scope.org_id, scope.project_id, provider_id),
        ).fetchone()
        if latest is None:
            raise AipResearchJobNotFound("research provider not found in scope")
        if int(latest["revision"]) != revision:
            raise AipResearchJobBlocked("research provider revision is not current")
        return latest

    @staticmethod
    def _provider(scope: TenantScope, row: Any) -> ResearchProviderRevision:
        return ResearchProviderRevision(
            tenant=_tenant(scope),
            provider_id=row["provider_id"],
            revision=row["revision"],
            adapter_kind=row["adapter_kind"],
            capability_ref=ResourceRef(
                resource_type=row["capability_type"],
                resource_id=row["capability_id"],
                revision=row["capability_revision"],
                authority=row["capability_authority"],
            ),
            contract_hash=row["contract_hash"],
            callback_secret_ref_hash=row["callback_secret_ref_hash"],
            status=ResearchProviderStatus(row["status"]),
            source_hash=row["source_hash"],
            created_by=row["created_by"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _submission(scope: TenantScope, row: Any) -> ResearchSubmissionReceipt:
        return ResearchSubmissionReceipt(
            tenant=_tenant(scope),
            submission_receipt_id=row["submission_receipt_id"],
            job_id=row["job_id"],
            provider_execution_id=row["provider_execution_id"],
            provider_version=row["provider_version"],
            accepted_manifest_hash=row["accepted_manifest_hash"],
            source_hash=row["source_hash"],
            observed_at=row["observed_at"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _artifact(scope: TenantScope, row: Any) -> ResearchArtifactReceipt:
        return ResearchArtifactReceipt(
            tenant=_tenant(scope),
            artifact_receipt_id=row["artifact_receipt_id"],
            artifact=ArtifactRef(
                artifact_id=row["artifact_id"],
                artifact_type=row["artifact_type"],
                revision=None,
                content_hash=row["content_hash"],
            ),
            job_id=row["job_id"],
            provider_execution_id=row["provider_execution_id"],
            content_ref=row["content_ref"],
            media_type=row["media_type"],
            source_hash=row["source_hash"],
            observed_at=row["observed_at"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _delivery(scope: TenantScope, row: Any) -> ResearchDeliveryReceipt:
        return ResearchDeliveryReceipt(
            tenant=_tenant(scope),
            receipt_id=row["receipt_id"],
            job_id=row["job_id"],
            receipt_kind=row["receipt_kind"],
            status=row["status"],
            artifact_ids=list(row["artifact_ids"]),
            reason_code=row["reason_code"],
            source_hash=row["source_hash"],
            observed_at=row["observed_at"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _submission_payload(row: Any) -> dict[str, Any]:
        return {
            "jobId": row["job_id"],
            "providerExecutionId": row["provider_execution_id"],
            "providerVersion": row["provider_version"],
            "acceptedManifestHash": row["accepted_manifest_hash"],
            "sourceHash": row["source_hash"],
            "observedAt": row["observed_at"].isoformat().replace("+00:00", "Z"),
        }

    @staticmethod
    def _artifact_payload(row: Any) -> dict[str, Any]:
        return {
            "jobId": row["job_id"],
            "providerExecutionId": row["provider_execution_id"],
            "artifactType": row["artifact_type"],
            "contentRef": row["content_ref"],
            "mediaType": row["media_type"],
            "contentHash": row["content_hash"],
            "schemaRef": row["schema_ref"],
            "sourceHash": row["source_hash"],
            "observedAt": row["observed_at"].isoformat().replace("+00:00", "Z"),
        }

    @staticmethod
    def _delivery_payload(row: Any) -> dict[str, Any]:
        return {
            "jobId": row["job_id"],
            "providerExecutionId": row["provider_execution_id"],
            "receiptKind": row["receipt_kind"],
            "status": row["status"],
            "artifactIds": list(row["artifact_ids"]),
            "reasonCode": row["reason_code"],
            "sourceHash": row["source_hash"],
            "observedAt": row["observed_at"].isoformat().replace("+00:00", "Z"),
        }


def _tenant(scope: TenantScope) -> TenantContext:
    return TenantContext(org_id=scope.org_id, project_id=scope.project_id)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _id(prefix: str, scope: TenantScope, *parts: str) -> str:
    material = ":".join((scope.org_id, scope.project_id, *parts))
    return f"{prefix}-{hashlib.sha256(material.encode()).hexdigest()[:28]}"


__all__ = [
    "AipResearchJobBlocked",
    "AipResearchJobConflict",
    "AipResearchJobError",
    "AipResearchJobNotFound",
    "AipResearchJobPersistenceError",
    "AipResearchJobStore",
    "ResearchJobProjectionFacts",
]

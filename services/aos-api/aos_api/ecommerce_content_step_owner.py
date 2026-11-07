"""Exact settled-content source for the original AIP generation step.

Reading this proof has no execution authority. The later StepRun Owner must
revalidate the current installation and perform all AIP transitions atomically.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import asyncio

from aos_api.ecommerce_content_execution_composition import (
    CurrentContentContextReader, CurrentContentStatusReader, CurrentContentPreparation,
)
from aos_api.ecommerce_content_execution_journal import ContentExecutionJournal, ContentExecutionConflict
from aos_api.aip_task_store import AipTaskStore
from aos_api.ecommerce_growth_host_ports import HostTransaction, EcommerceGrowthHostError
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory, _request_hash
from aos_api.ecommerce_growth_runtime_connection import connect_read_only, connect_serializable
from aos_api.tenant_scope import TenantScope


class ContentStepConflict(RuntimeError):
    """A recorded Provider result cannot yet back one canonical StepRun."""


class ContentStepUnknown(ContentStepConflict):
    """The internal commit boundary cannot yet be independently reconciled."""


@dataclass(frozen=True)
class ContentGenerationStepProof:
    reservation_id: str
    run_id: str
    task_id: str
    artifact_id: str
    artifact_hash: str
    provider_receipt_ref: dict
    usage_receipt_refs: tuple[dict, ...]


class ContentGenerationStepSource:
    """Read-only reconciliation of one settled result to its original Run."""

    def __init__(self, *, status_reader=None, journal=None, context_reader=None):
        self.status_reader = status_reader or CurrentContentStatusReader()
        self.journal = journal or ContentExecutionJournal()
        self.context_reader = context_reader or CurrentContentContextReader()

    def read(self, conn, scope: TenantScope, reservation_id: str) -> ContentGenerationStepProof:
        if (
            type(scope) is not TenantScope or type(reservation_id) is not str
            or not reservation_id or reservation_id.strip() != reservation_id
        ):
            raise ValueError("exact scoped content reservation required")
        if self.status_reader(conn, scope, reservation_id) != "COMPLETED":
            raise ContentStepConflict("content result must be independently COMPLETED")
        row = conn.execute(
            """SELECT invocation_id,task_ref,state,provider_receipt_ref,usage_receipt_refs
                 FROM public.aip_budget_reservation
                WHERE org_id=%s AND project_id=%s AND reservation_id=%s""",
            (*scope.key, reservation_id),
        ).fetchone()
        if row is None or row["state"] != "settled":
            raise ContentStepConflict("settled content reservation missing")
        evidence = self.journal.read(conn, scope, reservation_id)
        if evidence is None or evidence["result"] is None:
            raise ContentStepConflict("persisted content result missing")
        command = evidence["command"]
        context = self.context_reader(conn, scope, command)
        task_id = row["task_ref"].get("resourceId") if type(row["task_ref"]) is dict else None
        if (
            type(command) is not dict
            or type(command.get("authorityRefs")) is not dict
            or type(command["authorityRefs"].get("task")) is not dict
            or command["authorityRefs"]["task"].get("resourceId") != task_id
            or type(task_id) is not str or not task_id
            or type(context) is not dict or type(context.get("runId")) is not str
            or not context["runId"]
            or type(row["provider_receipt_ref"]) is not dict
            or type(row["usage_receipt_refs"]) is not list
            or len(row["usage_receipt_refs"]) != 2
        ):
            raise ContentStepConflict("content source authority drifted")
        invocation_id = str(row["invocation_id"])
        artifact_id = "artifact-" + hashlib.sha256(invocation_id.encode()).hexdigest()[:20]
        artifact = conn.execute(
            """SELECT artifact_id,run_id,artifact_type,content_hash,source
                 FROM public.aip_artifact
                WHERE org_id=%s AND project_id=%s AND artifact_id=%s""",
            (*scope.key, artifact_id),
        ).fetchone()
        if (
            artifact is None or artifact["artifact_id"] != artifact_id
            or artifact["run_id"] != context["runId"]
            or artifact["artifact_type"] != "ecommerce_content"
            or type(artifact["content_hash"]) is not str
            or len(artifact["content_hash"]) != 64
            or type(artifact["source"]) is not dict
            or artifact["source"].get("invocationId") != invocation_id
        ):
            raise ContentStepConflict("content Artifact is not the original Run output")
        run = conn.execute(
            """SELECT r.task_id,r.status,r.plan_revision_id,t.status AS task_status,
                      p.approval_status,p.steps
                 FROM public.aip_task_run r
                 JOIN public.aip_task t ON t.org_id=r.org_id AND t.project_id=r.project_id
                                     AND t.task_id=r.task_id
                 JOIN public.aip_plan_revision p ON p.org_id=r.org_id AND p.project_id=r.project_id
                     AND p.plan_revision_id=r.plan_revision_id AND p.task_id=r.task_id
                WHERE r.org_id=%s AND r.project_id=%s AND r.run_id=%s""",
            (*scope.key, context["runId"]),
        ).fetchone()
        if (
            run is None or run["task_id"] != task_id or run["status"] != "running"
            or run["task_status"] != "executing"
            or run["approval_status"] != "approved"
            or type(run["steps"]) is not list
            or [step.get("stepKey") for step in run["steps"]]
                != ["content_generate", "content_review"]
        ):
            raise ContentStepConflict("content original TaskRun/Plan is not current")
        return ContentGenerationStepProof(
            reservation_id=reservation_id, run_id=context["runId"], task_id=task_id,
            artifact_id=artifact_id, artifact_hash=artifact["content_hash"],
            provider_receipt_ref=row["provider_receipt_ref"],
            usage_receipt_refs=tuple(row["usage_receipt_refs"]),
        )


class ContentGenerationStepOwner:
    """Complete only the internal AIP step for one already-settled content result.

    No Provider call or public worker loop lives here. A commit/readback error
    escapes to the caller as unknown; it must be reconciled before any rerun.
    """

    actor = "ecommerce-content-generation-step-owner"

    def __init__(self, *, source=None, connect_write=connect_serializable,
                 connect_read=connect_read_only, store_factory=AipTaskStore):
        self.source = source or ContentGenerationStepSource()
        self.connect_write = connect_write
        self.connect_read = connect_read
        self.store_factory = store_factory

    @staticmethod
    def _current_dispatch(conn, scope: TenantScope, reservation_id: str) -> None:
        evidence = ContentExecutionJournal().read(conn, scope, reservation_id)
        command = None if evidence is None else evidence["command"]
        if type(command) is not dict or type(command.get("idempotencyKey")) is not str:
            raise ContentStepConflict("original content command is unavailable")
        row = CurrentContentPreparation._runtime_row(conn, scope, command)
        if (
            row is None or row["request_hash"] != _request_hash(command)
            or type(row["response"]) is not dict
            or row["response"].get("state") != "PENDING"
        ):
            raise ContentStepConflict("original content runtime Receipt drifted")
        snapshot = CurrentContentPreparation._lock_dispatch(conn, scope, row)
        if snapshot.runtime_revision != row["runtime_revision"]:
            raise ContentStepConflict("content installation revision drifted")

    def _complete_transaction(
        self, conn, scope: TenantScope, proof: ContentGenerationStepProof,
    ) -> str | None:
        existing = conn.execute(
            """SELECT step_run_id,status FROM public.aip_step_run
                WHERE org_id=%s AND project_id=%s AND run_id=%s
                  AND step_key='content_generate'
                ORDER BY attempt DESC LIMIT 1 FOR UPDATE""",
            (*scope.key, proof.run_id),
        ).fetchone()
        if existing is not None:
            if existing["status"] == "succeeded":
                return None  # independent readback still required
            raise ContentStepConflict("existing content generation attempt needs reconciliation")
        store = self.store_factory(
            TransactionBoundConnectFactory(HostTransaction(conn), scope)
        )
        lease = store.claim_step(
            scope, proof.run_id, "content_generate", self.actor, lease_seconds=60
        )
        artifact_ref = {
            "resourceType": "ArtifactRevision", "resourceId": proof.artifact_id,
            "revision": 1, "contentHash": "sha256:" + proof.artifact_hash,
        }
        phases = (
            ("think", {"kind": "settled_content_reconciliation",
                       "reservationId": proof.reservation_id}),
            ("act", {"kind": "already_completed_provider_result",
                     "providerReceiptRef": proof.provider_receipt_ref}),
            ("verify", {"passed": True,
                        "usageReceiptRefs": list(proof.usage_receipt_refs)}),
            ("observe", {"reservationId": proof.reservation_id,
                         "artifactRef": artifact_ref,
                         "providerReceiptRef": proof.provider_receipt_ref}),
        )
        for phase, payload in phases:
            store.record_step_phase(
                scope, lease.step_run_id, self.actor, lease.fence,
                self.actor, phase, payload,
            )
        return store.complete_step(
            scope, lease.step_run_id, self.actor, lease.fence, self.actor
        )

    @staticmethod
    def _readback(conn, scope: TenantScope, proof: ContentGenerationStepProof,
                  checkpoint_id: str | None) -> dict[str, str]:
        step = conn.execute(
            """SELECT step_run_id,status,attempt,think_ref,action_ref,verify_ref,observe_ref
                 FROM public.aip_step_run
                WHERE org_id=%s AND project_id=%s AND run_id=%s
                  AND step_key='content_generate'
                ORDER BY attempt DESC LIMIT 1""",
            (*scope.key, proof.run_id),
        ).fetchone()
        if (
            step is None or step["status"] != "succeeded"
            or any(step[key] is None for key in
                   ("think_ref", "action_ref", "verify_ref", "observe_ref"))
        ):
            raise ContentStepUnknown("content StepRun commit/readback unknown")
        checkpoint = conn.execute(
            """SELECT checkpoint_id,state_snapshot_ref FROM public.aip_checkpoint
                WHERE org_id=%s AND project_id=%s AND run_id=%s
                  AND step_key='content_generate' AND attempt=%s""",
            (*scope.key, proof.run_id, step["attempt"]),
        ).fetchone()
        observation = conn.execute(
            """SELECT payload FROM public.aip_evidence
                WHERE org_id=%s AND project_id=%s AND evidence_id=%s
                  AND run_id=%s AND evidence_type='taor.observe'""",
            (*scope.key, step["observe_ref"]["evidenceId"], proof.run_id),
        ).fetchone()
        expected_ref = {
            "resourceType": "ArtifactRevision", "resourceId": proof.artifact_id,
            "revision": 1, "contentHash": "sha256:" + proof.artifact_hash,
        }
        if (
            checkpoint is None or (
                checkpoint_id is not None and checkpoint["checkpoint_id"] != checkpoint_id
            )
            or type(checkpoint["state_snapshot_ref"]) is not dict
            or checkpoint["state_snapshot_ref"].get("stepRunId") != step["step_run_id"]
            or checkpoint["state_snapshot_ref"].get("status") != "succeeded"
            or observation is None or type(observation["payload"]) is not dict
            or observation["payload"].get("stepRunId") != step["step_run_id"]
            or observation["payload"].get("payload", {}).get("artifactRef") != expected_ref
            or observation["payload"].get("payload", {}).get("reservationId")
                != proof.reservation_id
        ):
            raise ContentStepUnknown("content StepRun checkpoint/Artifact readback unknown")
        return {"status": "GENERATION_STEP_SUCCEEDED", "runId": proof.run_id,
                "stepRunId": step["step_run_id"],
                "checkpointId": checkpoint["checkpoint_id"]}

    def run_one(self, scope: TenantScope, reservation_id: str) -> dict[str, str]:
        with self.connect_write(scope) as conn:
            proof = self.source.read(conn, scope, reservation_id)
            self._current_dispatch(conn, scope, reservation_id)
            checkpoint_id = self._complete_transaction(conn, scope, proof)
        # A failed independent read is an unknown boundary, never permission to
        # call Provider or claim another attempt.
        with self.connect_read(scope) as conn:
            return self._readback(conn, scope, proof, checkpoint_id)

    def list_pending(self, scope: TenantScope, *, limit: int = 16) -> list[str]:
        if type(scope) is not TenantScope or type(limit) is not int or not 1 <= limit <= 16:
            raise ValueError("bounded scoped content step selector required")
        with self.connect_read(scope) as conn:
            rows = conn.execute(
                """SELECT b.reservation_id
                     FROM public.aip_budget_reservation b
                     JOIN public.ecommerce_content_execution_result result
                       ON result.org_id=b.org_id AND result.project_id=b.project_id
                      AND result.reservation_id=b.reservation_id
                     JOIN public.aip_artifact a
                       ON a.org_id=b.org_id AND a.project_id=b.project_id
                      AND a.artifact_type='ecommerce_content'
                      AND a.source->>'invocationId'=b.invocation_id::text
                     JOIN public.aip_task_run r
                       ON r.org_id=a.org_id AND r.project_id=a.project_id
                      AND r.run_id=a.run_id AND r.task_id=b.task_ref->>'resourceId'
                    WHERE b.org_id=%s AND b.project_id=%s AND b.state='settled'
                      AND b.operation_id='ecommerce_growth_content_generate'
                      AND r.status='running'
                      AND NOT EXISTS(
                          SELECT 1 FROM public.aip_step_run step
                           WHERE step.org_id=r.org_id AND step.project_id=r.project_id
                             AND step.run_id=r.run_id AND step.step_key='content_generate')
                    ORDER BY result.recorded_at,b.reservation_id LIMIT %s""",
                (*scope.key, limit),
            ).fetchall()
        values = [str(row["reservation_id"]) for row in rows]
        if len(values) != len(set(values)) or any(not value for value in values):
            raise ContentStepConflict("content step selector identity drifted")
        return values

    def run_once(self, scope: TenantScope, *, limit: int = 16) -> list[dict[str, str]]:
        results = []
        for reservation_id in self.list_pending(scope, limit=limit):
            try:
                result = self.run_one(scope, reservation_id)
            except ContentStepUnknown:
                raise  # unknown commit/readback stops the entire worker
            except (ContentStepConflict, ContentExecutionConflict, EcommerceGrowthHostError):
                results.append({"reservationId": reservation_id,
                                "status": "BLOCKED_CURRENT_AUTHORITY"})
                continue
            results.append({"reservationId": reservation_id, "status": result["status"]})
        return results

    async def serve(self, stop, *, host_ready, interval_seconds: int = 15) -> None:
        if type(interval_seconds) is not int or not 1 <= interval_seconds <= 300:
            raise ValueError("content step worker interval invalid")
        scope = TenantScope("org-org", "dev-project")
        while not stop.is_set():
            if not host_ready():
                raise RuntimeError("content step Runtime Host unavailable")
            await asyncio.to_thread(self.run_once, scope)
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
            except TimeoutError:
                pass

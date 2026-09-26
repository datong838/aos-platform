"""Exact settled-content source for the original AIP generation step.

Reading this proof has no execution authority. The later StepRun Owner must
revalidate the current installation and perform all AIP transitions atomically.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib

from aos_api.ecommerce_content_execution_composition import (
    CurrentContentContextReader, CurrentContentStatusReader,
)
from aos_api.ecommerce_content_execution_journal import ContentExecutionJournal
from aos_api.tenant_scope import TenantScope


class ContentStepConflict(RuntimeError):
    """A recorded Provider result cannot yet back one canonical StepRun."""


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

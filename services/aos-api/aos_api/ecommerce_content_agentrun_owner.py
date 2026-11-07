"""One-attempt natural AgentRun handoff for an accepted content TaskRun."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from uuid import UUID, uuid4

from aos_api.aip_agent_registry_contracts import AgentRunRequest, CreateAgentRunRequest, VersionedAssetRef
from aos_api.aip_agent_run_service import AipAgentRunService
from aos_api.aip_contracts import ResourceRef
from aos_api.aip_model_runtime_contracts import ModelRuntimeReadiness
from aos_api.aip_model_runtime_resolver import AipModelRuntimeResolver
from aos_api.aip_model_runtime_store import AipModelRuntimeStore
from aos_api.aip_task_store import AipTaskStore, _canonical_hash
from aos_api.ecommerce_content_taskrun_owner import ContentTaskRunConflict, ContentTaskRunOwner
from aos_api.ecommerce_analyst_authority_store import canonical_hash
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import (
    ContentGenerateHostService, ReviewAdvanceHostService,
    TransactionBoundConnectFactory, _content_exact_ref,
)
from aos_api.ecommerce_growth_runtime_connection import connect_read_only, connect_serializable
from aos_api.tenant_scope import TenantScope


_PENDING = """SELECT i.review_key
  FROM public.ecommerce_growth_content_agentrun_intent i
  JOIN public.ecommerce_growth_content_taskrun_intent p
    ON p.org_id=i.org_id AND p.project_id=i.project_id AND p.review_key=i.review_key
   AND p.task_id=i.task_id AND p.plan_revision_id=i.plan_revision_id
   AND p.run_id=i.task_run_id AND p.review_receipt_ref=i.review_receipt_ref
  JOIN public.ecommerce_growth_runtime_command_receipt o
    ON o.org_id=i.org_id AND o.project_id=i.project_id
   AND o.operation_id='ecommerce_growth_review_advance'
   AND o.idempotency_key=i.review_key
  JOIN public.extension_operation_dispatch_binding d
    ON d.org_id=o.org_id AND d.project_id=o.project_id
   AND d.operation_id=o.operation_id
  JOIN public.extension_runtime_binding b
    ON b.org_id=o.org_id AND b.project_id=o.project_id
   AND b.installation_id=o.installation_id AND b.generation=o.generation
  JOIN public.aip_task_run r
    ON r.org_id=i.org_id AND r.project_id=i.project_id
   AND r.run_id=i.task_run_id AND r.task_id=i.task_id
   AND r.plan_revision_id=i.plan_revision_id
  JOIN public.aip_task t
    ON t.org_id=r.org_id AND t.project_id=r.project_id AND t.task_id=r.task_id
 WHERE i.org_id=%s AND i.project_id=%s AND i.state='pending' AND i.attempt=0
   AND p.state='accepted' AND p.attempt=1
   AND r.status='running' AND t.status='executing'
   AND t.current_plan_revision_id=i.plan_revision_id
   AND o.response->'receiptRef'=i.review_receipt_ref
   AND o.response->>'decision'='ACCEPT'
   AND d.handler_kind='extension' AND d.operation_fence=false
   AND d.revision=o.dispatch_revision
   AND d.installation_id=o.installation_id AND d.generation=o.generation
   AND d.execution_epoch=o.execution_epoch
   AND d.cutover_group_id=o.cutover_group_id
   AND d.cutover_group_revision=o.cutover_group_revision
   AND b.revision=o.runtime_revision AND b.execution_epoch=o.execution_epoch
   AND b.desired_state='enabled' AND b.observed_state='ready'
   AND b.enabled=true AND b.operation_fence=false
 ORDER BY i.created_at,i.review_key LIMIT %s"""


class ContentAgentRunConflict(RuntimeError):
    """The accepted content TaskRun cannot authorize a new AgentRun."""


class ContentAgentRunOwner:
    actor = "ecommerce-growth-content-agentrun-owner"

    def __init__(self, *, connect_read=connect_read_only, connect_write=connect_serializable):
        self._connect_read = connect_read
        self._connect_write = connect_write

    def list_pending(self, scope: TenantScope, *, limit: int = 16) -> list[str]:
        if type(scope) is not TenantScope or type(limit) is not int or not 1 <= limit <= 16:
            raise ValueError("bounded content AgentRun selector and tenant scope required")
        with self._connect_read(scope) as conn:
            rows = conn.execute(_PENDING, (*scope.key, limit)).fetchall()
        values = [row["review_key"] for row in rows]
        if any(type(value) is not str or not value for value in values):
            raise ContentAgentRunConflict("content AgentRun selector identity drifted")
        return values

    def claim(self, scope: TenantScope, review_key: str) -> UUID | None:
        if type(scope) is not TenantScope or type(review_key) is not str or not review_key.strip():
            raise ValueError("content AgentRun claim needs scoped Review key")
        token = uuid4()
        with self._connect_write(scope) as conn:
            # The DB function verifies Review/Run. Re-lock the entire cutover
            # group before consuming the sole attempt.
            transaction = HostTransaction(conn)
            try:
                self._build_request(transaction, scope, review_key)
            except (ContentAgentRunConflict, ContentTaskRunConflict, ValueError):
                return None
            row = conn.execute(
                "SELECT public.ecommerce_growth_content_agentrun_claim_a0v_102(%s,%s) AS claimed",
                (review_key, token),
            ).fetchone()
            if row is None or row["claimed"] is not True:
                return None
            conn.commit()
        with self._connect_read(scope) as conn:
            readback = conn.execute(
                """SELECT state,attempt,claim_token
                     FROM public.ecommerce_growth_content_agentrun_intent
                    WHERE org_id=%s AND project_id=%s AND review_key=%s""",
                (*scope.key, review_key),
            ).fetchone()
        if readback is None or (
            readback["state"], readback["attempt"], readback["claim_token"]
        ) != ("claimed", 1, token):
            raise ContentAgentRunConflict("content AgentRun claim readback unknown")
        return token

    @staticmethod
    def _build_request(transaction: HostTransaction, scope: TenantScope,
                       review_key: str,
                       *, existing_agent_run_id: str | None = None) -> CreateAgentRunRequest:
        origin, response = ContentTaskRunOwner._origin(transaction, scope, review_key)
        row = transaction.execute(
            """SELECT p.review_receipt_ref,p.task_id,p.plan_revision_id,p.run_id,
                      i.task_run_id,i.plan_revision_id AS next_plan_id,i.task_id AS next_task_id
                 FROM public.ecommerce_growth_content_taskrun_intent p
                 JOIN public.ecommerce_growth_content_agentrun_intent i
                   ON i.org_id=p.org_id AND i.project_id=p.project_id
                  AND i.review_key=p.review_key
                WHERE p.org_id=%s AND p.project_id=%s AND p.review_key=%s
                  AND p.state='accepted' AND p.attempt=1 FOR SHARE OF p,i""",
            (*scope.key, review_key),
        ).fetchone()
        if (
            row is None or row["review_receipt_ref"] != origin["target_receipt_ref"]
            or row["task_id"] != response["taskRef"]["resourceId"]
            or row["task_run_id"] != row["run_id"]
            or row["next_plan_id"] != row["plan_revision_id"]
            or row["next_task_id"] != row["task_id"]
        ):
            raise ContentAgentRunConflict("accepted content TaskRun lineage drifted")
        authorities = {
            name: _content_exact_ref(response[key], kind)
            for name, key, kind in (
                ("handoff", "handoffRef", "HandoffReceipt"),
                ("task", "taskRef", "Task"),
                ("brief", "briefRef", "TaskBriefRevision"),
                ("growth_plan", "growthPlanRef", "GrowthPlanRevision"),
            )
        }
        source_values = [item["artifactRef"] for item in response["artifactBindings"]]
        if ContentGenerateHostService._review_receipt(
            transaction, scope, authorities, source_values
        ) != response:
            raise ContentAgentRunConflict("content Review changed")
        approved = ReviewAdvanceHostService._revalidate_growth_plan(
            transaction=transaction, scope=scope,
            command={"growthPlanRef": response["growthPlanRef"]},
        )
        if approved.sales_weapon_method is None:
            raise ContentAgentRunConflict("approved content method unavailable")
        ContentGenerateHostService._task_brief(
            transaction, scope, authorities, source_values, approved_plan=approved
        )
        checked = transaction.execute("SELECT clock_timestamp() AS checked_at").fetchone()
        if checked is None:
            raise ContentAgentRunConflict("content AgentRun clock unavailable")
        method = approved.sales_weapon_method
        ReviewAdvanceHostService._require_sales_weapon_method(
            transaction=transaction, scope=scope,
            command={
                "cutoffAt": method.source_cutoff_at.isoformat(),
                "expiresAt": (method.source_cutoff_at + timedelta(days=7)).isoformat(),
                "markings": ["internal"],
                "taskSpec": ReviewAdvanceHostService._sales_weapon_task_values(method),
            },
            plan=approved, checked_at=checked["checked_at"],
        )
        assignment = ContentTaskRunOwner._assignment(transaction, scope)
        bound = TransactionBoundConnectFactory(transaction, scope)
        timeline = AipTaskStore(bound).timeline(scope, row["run_id"])
        run, task, plan = timeline.run, timeline.task, timeline.plan
        plan_payload = {
            "steps": [item.model_dump(mode="json", by_alias=True) for item in plan.steps],
            "dependencies": plan.dependencies, "risk": plan.risk,
        }
        step = plan.steps[0] if len(plan.steps) == 2 else None
        if (
            run.id != row["run_id"] or run.task_id != task.id
            or run.plan_revision_id != plan.id or plan.id != row["plan_revision_id"]
            or plan.task_id != task.id or task.id != row["task_id"]
            or run.status.value != "running" or task.status.value != "executing"
            or plan.approval_status != "approved" or timeline.steps
            or plan.content_hash != _canonical_hash(plan_payload)
            or step is None or step.step_key != "content_generate"
            or plan.steps[1].step_key != "content_review"
            or step.responsibility_slot_ids != ["content.generate"]
            or step.assignee_refs != [assignment["assignee"]]
            or step.capability_refs != assignment["capabilities"]
            or plan.risk.get("responsibilityPlanRef") != assignment["plan_ref"]
            or plan.risk.get("reviewReceiptRef") != response["receiptRef"]
            or assignment["plan_ref"] not in plan.dependencies
        ):
            raise ContentAgentRunConflict("current content Plan/Run assignment drifted")
        existing_agents = transaction.execute(
            """SELECT agent_run_id FROM public.aip_agent_run
                WHERE org_id=%s AND project_id=%s AND task_run_id=%s LIMIT 2""",
            (*scope.key, run.id),
        ).fetchall()
        if (existing_agent_run_id is None and existing_agents) or (
            existing_agent_run_id is not None
            and [item["agent_run_id"] for item in existing_agents] != [existing_agent_run_id]
        ):
            raise ContentAgentRunConflict("content TaskRun already has an AgentRun; reconcile")
        agent_id = assignment["assignee"].resource_id
        skill_rows = transaction.execute(
            """SELECT b.binding_id,b.capability_refs,s.skill_id,s.revision,
                      s.content_hash AS skill_hash,s.required_capabilities,
                      s.logic_revision_ref,s.model_route_ref,s.runtime_policy_ref
                 FROM public.aip_skill_binding b
                 JOIN public.aip_skill_template_revision s
                   ON s.skill_id=b.skill_id AND s.revision=b.skill_revision
                WHERE b.org_id=%s AND b.project_id=%s AND b.instance_id=%s
                  AND b.status='active' AND s.lifecycle='published'
                ORDER BY b.binding_id LIMIT 17 FOR SHARE OF b""",
            (*scope.key, agent_id),
        ).fetchall()
        needed = {item.resource_id for item in assignment["capabilities"]}
        eligible = [item for item in skill_rows
                    if isinstance(item["required_capabilities"], list)
                    and len(item["required_capabilities"]) == len(needed)
                    and set(item["required_capabilities"]) == needed]
        if len(skill_rows) > 16 or len(eligible) != 1:
            raise ContentAgentRunConflict("content published Skill binding unavailable or ambiguous")
        skill = eligible[0]
        logic = VersionedAssetRef.model_validate(skill["logic_revision_ref"])
        route = VersionedAssetRef.model_validate(skill["model_route_ref"])
        policy = VersionedAssetRef.model_validate(skill["runtime_policy_ref"])
        resolved = AipModelRuntimeResolver(AipModelRuntimeStore(bound)).resolve(
            scope, route.asset_id, now=checked["checked_at"]
        )
        if (resolved.readiness is not ModelRuntimeReadiness.READY
                or resolved.route != route or resolved.policy != policy):
            raise ContentAgentRunConflict("content exact ModelRoute is not READY")
        agent_ref = _content_exact_ref({
            "resourceType": "AgentInstanceRevision", "resourceId": agent_id,
            "revision": int(assignment["assignee"].revision),
            "contentHash": "sha256:" + assignment["agent_hash"],
        }, "AgentInstanceRevision")
        input_refs = [response["briefRef"], *source_values]
        return CreateAgentRunRequest(
            agent_run_id="content-agent-" + canonical_hash({
                "tenant": scope.key, "reviewKey": review_key,
                "taskRunId": run.id, "planRevisionId": plan.id,
            })[:40],
            task_run_ref=ResourceRef(resource_type="TaskRun", resource_id=run.id,
                                     revision=str(run.version), authority="postgresql"),
            skill_binding_id=skill["binding_id"],
            run=AgentRunRequest(
                task_ref=ResourceRef(resource_type="Task", resource_id=task.id,
                                     revision=str(task.version), authority="postgresql"),
                plan_ref=ResourceRef(resource_type="PlanRevision", resource_id=plan.id,
                                     revision=str(plan.revision), authority="postgresql"),
                agent_instance=VersionedAssetRef(
                    asset_type="AgentInstance", asset_id=agent_ref.resource_id,
                    revision=agent_ref.revision,
                    content_hash=agent_ref.content_hash.removeprefix("sha256:"),
                ),
                skill=VersionedAssetRef(
                    asset_type="SkillTemplate", asset_id=skill["skill_id"],
                    revision=skill["revision"], content_hash=skill["skill_hash"],
                ),
                logic=logic, model_route=route, policy=policy,
                input_refs=[ResourceRef(
                    resource_type=ref["resourceType"], resource_id=ref["resourceId"],
                    revision=str(ref["revision"]), authority="postgresql",
                ) for ref in input_refs],
            ),
        )

    def execute_claim(self, scope: TenantScope, review_key: str, token: UUID) -> dict[str, str]:
        if type(scope) is not TenantScope or type(review_key) is not str or type(token) is not UUID:
            raise ValueError("exact claimed content AgentRun identity required")
        with self._connect_write(scope) as conn:
            transaction = HostTransaction(conn)
            request = self._build_request(transaction, scope, review_key)
            claim = transaction.execute(
                """SELECT state,attempt,claim_token,task_run_id,agent_run_id
                     FROM public.ecommerce_growth_content_agentrun_intent
                    WHERE org_id=%s AND project_id=%s AND review_key=%s FOR UPDATE""",
                (*scope.key, review_key),
            ).fetchone()
            if (claim is None or claim["state"] != "claimed" or claim["attempt"] != 1
                    or claim["claim_token"] != token or claim["agent_run_id"] is not None
                    or claim["task_run_id"] != request.task_run_ref.resource_id):
                raise ContentAgentRunConflict("content AgentRun claim drifted")
            clock = transaction.execute("SELECT clock_timestamp() AS checked_at").fetchone()
            if clock is None:
                raise ContentAgentRunConflict("content AgentRun clock unavailable")
            owner = AipAgentRunService(TransactionBoundConnectFactory(transaction, scope))
            run, receipt = owner._create_in_transaction(
                transaction, scope, request, idempotency_key=review_key,
                actor=self.actor, occurred_at=clock["checked_at"],
            )
            if (run.agent_run_id != request.agent_run_id or run.status.value != "queued"
                    or receipt.operation != "agent_run.create"
                    or receipt.idempotency_key != review_key
                    or receipt.result_ref.resource_id != run.agent_run_id):
                raise ContentAgentRunConflict("content AgentRun Owner Receipt drifted")
            ack = transaction.execute(
                "SELECT public.ecommerce_growth_content_agentrun_ack_a0v_102(%s,%s,%s) AS accepted",
                (review_key, token, run.agent_run_id),
            ).fetchone()
            if ack is None or ack["accepted"] is not True:
                raise ContentAgentRunConflict("content AgentRun ack unavailable")
            next_intent = transaction.execute(
                "SELECT public.ecommerce_growth_content_capacity_put_a0v_103(%s) AS pending",
                (review_key,),
            ).fetchone()
            if next_intent is None or next_intent["pending"] is not True:
                raise ContentAgentRunConflict("content capacity intent unavailable")
            conn.commit()
        with self._connect_read(scope) as conn:
            committed = conn.execute(
                """SELECT i.state,i.attempt,i.claim_token,i.agent_run_id,
                          a.status AS agent_status,receipt.status AS receipt_status,
                          next.state AS next_state,next.attempt AS next_attempt
                     FROM public.ecommerce_growth_content_agentrun_intent i
                     JOIN public.ecommerce_growth_content_capacity_intent next
                       ON next.org_id=i.org_id AND next.project_id=i.project_id
                      AND next.review_key=i.review_key
                      AND next.task_run_id=i.task_run_id
                      AND next.agent_run_id=i.agent_run_id
                     JOIN public.aip_agent_run a
                       ON a.org_id=i.org_id AND a.project_id=i.project_id
                      AND a.agent_run_id=i.agent_run_id AND a.task_run_id=i.task_run_id
                     JOIN public.aip_agent_registry_receipt receipt
                       ON receipt.org_id=i.org_id AND receipt.project_id=i.project_id
                      AND receipt.operation='agent_run.create'
                      AND receipt.idempotency_key=i.review_key
                      AND receipt.result_ref->>'resourceId'=a.agent_run_id
                    WHERE i.org_id=%s AND i.project_id=%s AND i.review_key=%s""",
                (*scope.key, review_key),
            ).fetchone()
        if committed is None or (
            committed["state"], committed["attempt"], committed["claim_token"],
            committed["agent_run_id"], committed["agent_status"], committed["receipt_status"],
            committed["next_state"], committed["next_attempt"],
        ) != ("accepted", 1, token, run.agent_run_id, "queued", "applied", "pending", 0):
            raise ContentAgentRunConflict("content AgentRun committed readback unknown")
        return {"status": "CONTENT_AGENT_RUN_QUEUED", "reviewKey": review_key,
                "agentRunId": run.agent_run_id}

    def run_once(self, scope: TenantScope, *, limit: int = 16) -> list[dict[str, str]]:
        results = []
        for review_key in self.list_pending(scope, limit=limit):
            token = self.claim(scope, review_key)
            if token is not None:
                # A failed/unknown execute leaves the single claim spent.
                results.append(self.execute_claim(scope, review_key, token))
        return results

    async def serve(self, stop, *, host_ready, interval_seconds: int = 15) -> None:
        if type(interval_seconds) is not int or not 1 <= interval_seconds <= 300:
            raise ValueError("content AgentRun worker interval invalid")
        scope = TenantScope("org-org", "dev-project")
        while not stop.is_set():
            if not host_ready():
                raise RuntimeError("content AgentRun Runtime Host unavailable")
            await asyncio.to_thread(self.run_once, scope)
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
            except TimeoutError:
                pass


__all__ = ["ContentAgentRunOwner", "ContentAgentRunConflict"]

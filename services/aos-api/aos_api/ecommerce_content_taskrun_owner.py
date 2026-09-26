"""One-attempt natural content Plan/Run startup from a durable exact Review."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

from aos_api.aip_contracts import PlanStep
from aos_api.aip_task_models import CreatePlanRevisionRequest, CreateTaskRunRequest
from aos_api.aip_task_store import AipTaskStore
from aos_api.ecommerce_growth_host_ports import HostTransaction, LockedEcommerceGrowthHostPort
from aos_api.ecommerce_growth_runtime_adapters import (
    ContentGenerateHostService,
    ReviewAdvanceHostService,
    TransactionBoundConnectFactory,
    _content_exact_ref,
)
from aos_api.ecommerce_growth_runtime_connection import connect_read_only, connect_serializable
from aos_api.tenant_scope import TenantScope


_PENDING = """SELECT i.review_key
  FROM public.ecommerce_growth_content_taskrun_intent i
  JOIN public.ecommerce_growth_runtime_command_receipt r
    ON r.org_id=i.org_id AND r.project_id=i.project_id
   AND r.operation_id='ecommerce_growth_review_advance'
   AND r.idempotency_key=i.review_key
  JOIN public.extension_operation_dispatch_binding d
    ON d.org_id=r.org_id AND d.project_id=r.project_id
   AND d.operation_id=r.operation_id
  JOIN public.extension_runtime_binding b
    ON b.org_id=r.org_id AND b.project_id=r.project_id
   AND b.installation_id=r.installation_id AND b.generation=r.generation
  JOIN public.aip_task t
    ON t.org_id=i.org_id AND t.project_id=i.project_id AND t.task_id=i.task_id
  JOIN public.aip_task_brief_revision brief
    ON brief.org_id=i.org_id AND brief.project_id=i.project_id
   AND brief.brief_id=i.brief_id AND brief.revision=1 AND brief.task_id=i.task_id
 WHERE i.org_id=%s AND i.project_id=%s AND i.state='pending' AND i.attempt=0
   AND t.status='pending' AND t.version=1 AND t.current_plan_revision_id IS NULL
   AND brief.schema_ref->>'resourceId'='schema://aos/ecommerce/content-campaign-brief/v2'
   AND i.review_receipt_ref=r.target_receipt_ref
   AND i.origin_request_hash=r.request_hash
   AND r.response->'receiptRef'=r.target_receipt_ref
   AND r.response->>'decision'='ACCEPT'
   AND d.handler_kind='extension' AND d.operation_fence=false
   AND d.revision=r.dispatch_revision
   AND d.installation_id=r.installation_id AND d.generation=r.generation
   AND d.execution_epoch=r.execution_epoch
   AND d.cutover_group_id=r.cutover_group_id
   AND d.cutover_group_revision=r.cutover_group_revision
   AND b.revision=r.runtime_revision AND b.execution_epoch=r.execution_epoch
   AND b.desired_state='enabled' AND b.observed_state='ready'
   AND b.enabled=true AND b.operation_fence=false
 ORDER BY i.created_at,i.review_key LIMIT %s"""


class ContentTaskRunConflict(RuntimeError):
    """A current exact Review cannot authorize a new content Run."""


class ContentTaskRunOwner:
    """Claim once, then use the existing AIP owner in one serializable transaction."""

    actor = "ecommerce-growth-content-taskrun-owner"

    def __init__(self, *, connect_read=connect_read_only, connect_write=connect_serializable):
        self._connect_read = connect_read
        self._connect_write = connect_write

    def list_pending(self, scope: TenantScope, *, limit: int = 16) -> list[str]:
        if type(scope) is not TenantScope or type(limit) is not int or not 1 <= limit <= 16:
            raise ValueError("bounded content TaskRun selector and tenant scope required")
        with self._connect_read(scope) as conn:
            rows = conn.execute(_PENDING, (*scope.key, limit)).fetchall()
        values = [row["review_key"] for row in rows]
        if any(type(value) is not str or not value for value in values):
            raise ContentTaskRunConflict("content TaskRun selector identity drifted")
        return values

    def claim(self, scope: TenantScope, review_key: str) -> UUID | None:
        if type(scope) is not TenantScope or type(review_key) is not str or not review_key.strip():
            raise ValueError("content TaskRun claim needs a scoped Review key")
        token = uuid4()
        with self._connect_write(scope) as conn:
            # Do not spend the one durable attempt when the full cutover group
            # is not currently executable, even if the review row alone is ready.
            self._origin(HostTransaction(conn), scope, review_key)
            row = conn.execute(
                "SELECT public.ecommerce_growth_content_taskrun_claim_a0v_101(%s,%s) AS claimed",
                (review_key, token),
            ).fetchone()
            if row is None or row["claimed"] is not True:
                return None
            conn.commit()
        with self._connect_read(scope) as conn:
            readback = conn.execute(
                """SELECT state,attempt,claim_token FROM public.ecommerce_growth_content_taskrun_intent
                    WHERE org_id=%s AND project_id=%s AND review_key=%s""",
                (*scope.key, review_key),
            ).fetchone()
        if readback is None or (readback["state"], readback["attempt"], readback["claim_token"]) != (
            "claimed", 1, token
        ):
            raise ContentTaskRunConflict("content TaskRun claim readback drifted")
        return token

    @staticmethod
    def _origin(transaction: HostTransaction, scope: TenantScope, review_key: str):
        origins = transaction.execute(
            """SELECT request_hash,response,target_receipt_ref,dispatch_revision,
                      installation_id,generation,execution_epoch,cutover_group_id,
                      cutover_group_revision,runtime_revision
                 FROM public.ecommerce_growth_runtime_command_receipt
                WHERE org_id=%s AND project_id=%s
                  AND operation_id='ecommerce_growth_review_advance'
                  AND idempotency_key=%s LIMIT 2""",
            (*scope.key, review_key),
        ).fetchall()
        if len(origins) != 1:
            raise ContentTaskRunConflict("content Review origin missing or ambiguous")
        origin = origins[0]
        response = origin["response"]
        if (
            type(response) is not dict or response.get("decision") != "ACCEPT"
            or response.get("receiptRef") != origin["target_receipt_ref"]
            or response.get("requestHash") != origin["request_hash"]
            or response.get("sideEffects", {}).get("taskRunCreatedCount") != 0
        ):
            raise ContentTaskRunConflict("content Review origin drifted")
        snapshot = LockedEcommerceGrowthHostPort._lock_and_revalidate(
            transaction, scope,
            SimpleNamespace(
                org_id=scope.org_id, project_id=scope.project_id,
                operation_id="ecommerce_growth_review_advance", handler_kind="extension",
                dispatch_revision=origin["dispatch_revision"],
                installation_id=origin["installation_id"], generation=origin["generation"],
                execution_epoch=origin["execution_epoch"],
                cutover_group_id=origin["cutover_group_id"],
                cutover_group_revision=origin["cutover_group_revision"],
            ),
        )
        if snapshot.runtime_revision != origin["runtime_revision"]:
            raise ContentTaskRunConflict("content Review runtime revision drifted")
        return origin, response

    def execute_claim(self, scope: TenantScope, review_key: str, token: UUID) -> dict[str, str]:
        if type(scope) is not TenantScope or type(review_key) is not str or type(token) is not UUID:
            raise ValueError("exact claimed content Review identity required")
        with self._connect_write(scope) as conn:
            transaction = HostTransaction(conn)
            origin, response = self._origin(transaction, scope, review_key)
            intent = transaction.execute(
                """SELECT review_receipt_ref,task_id,brief_id,origin_request_hash,state,
                          attempt,claim_token,plan_revision_id,run_id
                     FROM public.ecommerce_growth_content_taskrun_intent
                    WHERE org_id=%s AND project_id=%s AND review_key=%s FOR UPDATE""",
                (*scope.key, review_key),
            ).fetchone()
            if (
                intent is None or intent["state"] != "claimed" or intent["attempt"] != 1
                or intent["claim_token"] != token
                or intent["review_receipt_ref"] != origin["target_receipt_ref"]
                or intent["origin_request_hash"] != origin["request_hash"]
                or intent["task_id"] != response["taskRef"]["resourceId"]
                or intent["brief_id"] != response["briefRef"]["resourceId"]
                or intent["plan_revision_id"] is not None or intent["run_id"] is not None
            ):
                raise ContentTaskRunConflict("content TaskRun claim or Review binding drifted")
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
            exact_review = ContentGenerateHostService._review_receipt(
                transaction, scope, authorities, source_values
            )
            if exact_review != response:
                raise ContentTaskRunConflict("content Review exact response changed")
            approved = ReviewAdvanceHostService._revalidate_growth_plan(
                transaction=transaction, scope=scope,
                command={"growthPlanRef": response["growthPlanRef"]},
            )
            if approved.sales_weapon_method is None:
                raise ContentTaskRunConflict("content method is not approved")
            ContentGenerateHostService._task_brief(
                transaction, scope, authorities, source_values, approved_plan=approved
            )
            checked = transaction.execute("SELECT clock_timestamp() AS checked_at").fetchone()
            if checked is None:
                raise ContentTaskRunConflict("content TaskRun clock unavailable")
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
            store = AipTaskStore(TransactionBoundConnectFactory(transaction, scope))
            task = store.get_task(scope, intent["task_id"])
            if task.status.value != "pending" or task.version != 1 or task.current_plan_revision_id is not None:
                raise ContentTaskRunConflict("content Task is not pristine after Review")
            key = f"{review_key}:content-run"
            plan = store.create_plan(
                scope, self.actor, task.id, f"{key}:plan",
                CreatePlanRevisionRequest(
                    expected_task_version=1,
                    steps=[
                        PlanStep(step_key="content_generate", title="生成有来源的可读内容"),
                        PlanStep(step_key="content_review", title="人工审核可读内容"),
                    ],
                    dependencies=[response["growthPlanRef"], response["briefRef"]],
                    risk={
                        "reviewReceiptRef": response["receiptRef"],
                        "externalPublicationAllowed": False,
                        "providerInvocationAuthorized": False,
                    },
                ),
            )
            planned_task = store.get_task(scope, task.id)
            store.approve_plan(
                scope, self.actor, task.id, plan.revision,
                planned_task.version, plan.content_hash,
            )
            approved_task = store.get_task(scope, task.id)
            run = store.create_run(
                scope, self.actor, task.id, f"{key}:run",
                CreateTaskRunRequest(
                    plan_revision_id=plan.id, expected_task_version=approved_task.version,
                ),
            )
            store.start_run(
                scope, run.id, expected_run_version=run.version,
                expected_task_version=approved_task.version, actor=self.actor,
                idempotency_key=f"{key}:start",
            )
            ack = transaction.execute(
                "SELECT public.ecommerce_growth_content_taskrun_ack_a0v_101(%s,%s,%s,%s) AS accepted",
                (review_key, token, plan.id, run.id),
            ).fetchone()
            if ack is None or ack["accepted"] is not True:
                raise ContentTaskRunConflict("content TaskRun ack unavailable")
            readback = transaction.execute(
                """SELECT state,attempt,claim_token,plan_revision_id,run_id
                     FROM public.ecommerce_growth_content_taskrun_intent
                    WHERE org_id=%s AND project_id=%s AND review_key=%s""",
                (*scope.key, review_key),
            ).fetchone()
            if readback is None or (
                readback["state"], readback["attempt"], readback["claim_token"],
                readback["plan_revision_id"], readback["run_id"],
            ) != ("accepted", 1, token, plan.id, run.id):
                raise ContentTaskRunConflict("content TaskRun ack readback drifted")
            conn.commit()
        # The in-transaction readback above is not proof that the commit became
        # visible. A failed independent read is an unknown result, never a retry.
        with self._connect_read(scope) as conn:
            committed = conn.execute(
                """SELECT i.state,i.attempt,i.claim_token,i.plan_revision_id,i.run_id,
                          p.approval_status,r.status AS run_status
                     FROM public.ecommerce_growth_content_taskrun_intent i
                     JOIN public.aip_plan_revision p
                       ON p.org_id=i.org_id AND p.project_id=i.project_id
                      AND p.plan_revision_id=i.plan_revision_id AND p.task_id=i.task_id
                     JOIN public.aip_task_run r
                       ON r.org_id=i.org_id AND r.project_id=i.project_id
                      AND r.run_id=i.run_id AND r.task_id=i.task_id
                      AND r.plan_revision_id=i.plan_revision_id
                    WHERE i.org_id=%s AND i.project_id=%s AND i.review_key=%s""",
                (*scope.key, review_key),
            ).fetchone()
        if committed is None or (
            committed["state"], committed["attempt"], committed["claim_token"],
            committed["plan_revision_id"], committed["run_id"],
            committed["approval_status"], committed["run_status"],
        ) != ("accepted", 1, token, plan.id, run.id, "approved", "running"):
            raise ContentTaskRunConflict("content TaskRun committed readback unknown")
        return {"status": "CONTENT_RUN_RUNNING", "reviewKey": review_key,
                "planRevisionId": plan.id, "runId": run.id}

    def run_once(self, scope: TenantScope, *, limit: int = 16) -> list[dict[str, str]]:
        results = []
        for review_key in self.list_pending(scope, limit=limit):
            token = self.claim(scope, review_key)
            if token is None:
                continue
            # Any exception leaves the durable intent claimed. No automatic retry.
            results.append(self.execute_claim(scope, review_key, token))
        return results

    async def serve(self, stop, *, host_ready, interval_seconds: int = 15) -> None:
        if type(interval_seconds) is not int or not 1 <= interval_seconds <= 300:
            raise ValueError("content TaskRun worker interval invalid")
        scope = TenantScope("org-org", "dev-project")
        while not stop.is_set():
            if not host_ready():
                raise RuntimeError("content TaskRun Runtime Host unavailable")
            await asyncio.to_thread(self.run_once, scope)
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
            except TimeoutError:
                pass


__all__ = ["ContentTaskRunOwner", "ContentTaskRunConflict"]

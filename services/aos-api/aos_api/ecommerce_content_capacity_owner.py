"""One-attempt content AgentRun capacity start; unknown transitions stay claimed."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

from aos_api.aip_agent_registry_contracts import AgentRunStatus
from aos_api.aip_agent_run_service import AipAgentRunService
from aos_api.aip_model_runtime_resolver import AipModelRuntimeResolver
from aos_api.aip_model_runtime_store import AipModelRuntimeStore
from aos_api.ecommerce_content_agentrun_owner import ContentAgentRunConflict, ContentAgentRunOwner
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_connection import connect_read_only, connect_serializable
from aos_api.tenant_scope import TenantScope


class ContentCapacityConflict(RuntimeError):
    """Current authority does not allow a new capacity start."""


class ContentCapacityOwner:
    actor = "ecommerce-growth-content-capacity-owner"

    def __init__(self, *, connect_read=connect_read_only, connect_write=connect_serializable):
        self._connect_read = connect_read
        self._connect_write = connect_write

    def list_pending(self, scope: TenantScope, *, limit: int = 16) -> list[str]:
        if type(scope) is not TenantScope or type(limit) is not int or not 1 <= limit <= 16:
            raise ValueError("bounded content capacity selector and tenant scope required")
        with self._connect_read(scope) as conn:
            rows = conn.execute(
                """SELECT review_key FROM public.ecommerce_growth_content_capacity_intent
                    WHERE org_id=%s AND project_id=%s AND state='pending' AND attempt=0
                    ORDER BY created_at,review_key LIMIT %s""",
                (*scope.key, limit),
            ).fetchall()
        keys = [row["review_key"] for row in rows]
        if any(type(key) is not str or not key for key in keys):
            raise ContentCapacityConflict("content capacity selector identity drifted")
        return keys

    def _preflight(self, scope: TenantScope, review_key: str):
        # _build_request locks the current cutover/Plan group FOR SHARE.
        # PostgreSQL rejects those locks in a READ ONLY transaction.
        with self._connect_write(scope) as conn:
            row = conn.execute(
                """SELECT c.state,c.attempt,c.task_run_id,c.agent_run_id,
                          i.state AS prior_state,i.agent_run_id AS prior_agent_run_id
                     FROM public.ecommerce_growth_content_capacity_intent c
                     JOIN public.ecommerce_growth_content_agentrun_intent i
                       ON i.org_id=c.org_id AND i.project_id=c.project_id
                      AND i.review_key=c.review_key
                    WHERE c.org_id=%s AND c.project_id=%s AND c.review_key=%s""",
                (*scope.key, review_key),
            ).fetchone()
            if (row is None or row["state"] not in {"pending", "claimed"}
                    or row["prior_state"] != "accepted"
                    or row["agent_run_id"] != row["prior_agent_run_id"]):
                raise ContentCapacityConflict("content capacity lineage unavailable")
            request = ContentAgentRunOwner._build_request(
                HostTransaction(conn), scope, review_key,
                existing_agent_run_id=row["agent_run_id"],
            )
            if (request.agent_run_id != row["agent_run_id"]
                    or request.task_run_ref.resource_id != row["task_run_id"]):
                raise ContentCapacityConflict("content capacity AgentRun identity drifted")
            existing = conn.execute(
                """SELECT reservation_id FROM public.aip_model_capacity_reservation
                    WHERE org_id=%s AND project_id=%s AND agent_run_id=%s LIMIT 2""",
                (*scope.key, row["agent_run_id"]),
            ).fetchall()
            if existing:
                raise ContentCapacityConflict("content capacity already reserved; reconcile")
        service = AipAgentRunService(self._connect_read)
        current = service.get(scope, request.agent_run_id)
        if (current.status is not AgentRunStatus.QUEUED or current.version != 1
                or current.task_run_id != request.task_run_ref.resource_id
                or current.skill_binding_id != request.skill_binding_id
                or current.request != request.run):
            raise ContentCapacityConflict("queued AgentRun snapshot drifted")
        return current

    def claim(self, scope: TenantScope, review_key: str, *, token: UUID | None = None) -> UUID | None:
        if type(scope) is not TenantScope or type(review_key) is not str or not review_key.strip():
            raise ValueError("content capacity claim needs scoped Review key")
        if token is None:
            token = uuid4()
        if type(token) is not UUID:
            raise ValueError("content capacity claim token must be UUID")
        try:
            self._preflight(scope, review_key)
        except (ContentCapacityConflict, ContentAgentRunConflict, ValueError):
            return None
        with self._connect_write(scope) as conn:
            row = conn.execute(
                "SELECT public.ecommerce_growth_content_capacity_claim_a0v_103(%s,%s) AS claimed",
                (review_key, token),
            ).fetchone()
            if row is None or row["claimed"] is not True:
                return None
            conn.commit()
        with self._connect_read(scope) as conn:
            readback = conn.execute(
                """SELECT state,attempt,claim_token,agent_run_id
                     FROM public.ecommerce_growth_content_capacity_intent
                    WHERE org_id=%s AND project_id=%s AND review_key=%s""",
                (*scope.key, review_key),
            ).fetchone()
        if readback is None or (
            readback["state"], readback["attempt"], readback["claim_token"]
        ) != ("claimed", 1, token):
            raise ContentCapacityConflict("content capacity claim readback unknown")
        return token

    def _transition(self, scope: TenantScope, current):
        resolver = AipModelRuntimeResolver(AipModelRuntimeStore(self._connect_read))
        service = AipAgentRunService(self._connect_write, model_resolver=resolver)
        return service.transition(
            scope, current.agent_run_id, expected_version=current.version,
            from_status=AgentRunStatus.QUEUED, to_status=AgentRunStatus.RUNNING,
            actor=self.actor, occurred_at=datetime.now(UTC),
        )

    def execute_claim(self, scope: TenantScope, review_key: str, token: UUID) -> dict[str, str]:
        if type(scope) is not TenantScope or type(review_key) is not str or type(token) is not UUID:
            raise ValueError("exact claimed content capacity identity required")
        current = self._preflight(scope, review_key)
        with self._connect_read(scope) as conn:
            claim = conn.execute(
                """SELECT state,attempt,claim_token,agent_run_id
                     FROM public.ecommerce_growth_content_capacity_intent
                    WHERE org_id=%s AND project_id=%s AND review_key=%s""",
                (*scope.key, review_key),
            ).fetchone()
        if claim is None or (
            claim["state"], claim["attempt"], claim["claim_token"], claim["agent_run_id"]
        ) != ("claimed", 1, token, current.agent_run_id):
            raise ContentCapacityConflict("content capacity claim drifted")
        # The public Owner and capacity Gate have independent commits. Any exception
        # leaves this one-attempt claim frozen for read-only reconciliation.
        started = self._transition(scope, current)
        if started.status is not AgentRunStatus.RUNNING:
            raise ContentCapacityConflict("AgentRun start result unknown")
        with self._connect_write(scope) as conn:
            refreshed = ContentAgentRunOwner._build_request(
                HostTransaction(conn), scope, review_key,
                existing_agent_run_id=current.agent_run_id,
            )
            if (refreshed.agent_run_id != current.agent_run_id
                    or refreshed.run != current.request):
                raise ContentCapacityConflict("content capacity authority drifted after start")
            rows = conn.execute(
                """SELECT r.reservation_id FROM public.aip_model_capacity_reservation r
                    JOIN public.aip_agent_run a
                      ON a.org_id=r.org_id AND a.project_id=r.project_id
                     AND a.agent_run_id=r.agent_run_id
                    WHERE r.org_id=%s AND r.project_id=%s AND r.agent_run_id=%s
                      AND a.status='running' AND r.status IN ('reserved','consumed')
                      AND r.expires_at>clock_timestamp() LIMIT 2""",
                (*scope.key, current.agent_run_id),
            ).fetchall()
        if len(rows) != 1:
            raise ContentCapacityConflict("capacity start readback unknown")
        reservation_id = rows[0]["reservation_id"]
        with self._connect_write(scope) as conn:
            ack = conn.execute(
                "SELECT public.ecommerce_growth_content_capacity_ack_a0v_103(%s,%s,%s) AS accepted",
                (review_key, token, reservation_id),
            ).fetchone()
            if ack is None or ack["accepted"] is not True:
                raise ContentCapacityConflict("content capacity ack unavailable")
            next_intent = conn.execute(
                "SELECT public.ecommerce_growth_content_budget_command_put_a0v_104(%s) AS pending",
                (review_key,),
            ).fetchone()
            if next_intent is None or next_intent["pending"] is not True:
                raise ContentCapacityConflict("content budget command intent unavailable")
            conn.commit()
        with self._connect_read(scope) as conn:
            committed = conn.execute(
                """SELECT c.state,c.attempt,c.claim_token,c.agent_run_id,
                          c.capacity_reservation_id,n.state AS next_state,
                          n.attempt AS next_attempt
                     FROM public.ecommerce_growth_content_capacity_intent c
                     JOIN public.ecommerce_growth_content_budget_command_intent n
                       ON n.org_id=c.org_id AND n.project_id=c.project_id
                      AND n.review_key=c.review_key
                      AND n.agent_run_id=c.agent_run_id
                      AND n.capacity_reservation_id=c.capacity_reservation_id
                    WHERE c.org_id=%s AND c.project_id=%s AND c.review_key=%s""",
                (*scope.key, review_key),
            ).fetchone()
        if committed is None or (
            committed["state"], committed["attempt"], committed["claim_token"],
            committed["agent_run_id"], committed["capacity_reservation_id"],
            committed["next_state"], committed["next_attempt"],
        ) != ("accepted", 1, token, current.agent_run_id, reservation_id, "pending", 0):
            raise ContentCapacityConflict("content capacity committed readback unknown")
        return {"status": "CONTENT_CAPACITY_RESERVED", "reviewKey": review_key,
                "agentRunId": current.agent_run_id, "capacityReservationId": reservation_id}

    def run_once(self, scope: TenantScope, *, limit: int = 16) -> list[dict[str, str]]:
        results = []
        for review_key in self.list_pending(scope, limit=limit):
            token = self.claim(scope, review_key)
            if token is not None:
                results.append(self.execute_claim(scope, review_key, token))
        return results

    async def serve(self, stop, *, host_ready, interval_seconds: int = 15) -> None:
        if type(interval_seconds) is not int or not 1 <= interval_seconds <= 300:
            raise ValueError("content capacity worker interval invalid")
        scope = TenantScope("org-org", "dev-project")
        while not stop.is_set():
            if not host_ready():
                raise RuntimeError("content capacity Runtime Host unavailable")
            await asyncio.to_thread(self.run_once, scope)
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
            except TimeoutError:
                pass


__all__ = ["ContentCapacityOwner", "ContentCapacityConflict"]

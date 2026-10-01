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
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.ecommerce_content_budget_command_owner import ContentBudgetCommandOwner, ContentBudgetCommandConflict
from aos_api.aip_action_store import AipActionTransitionBlocked
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

    @staticmethod
    def _admit(transaction, scope, review_key, *, token=None):
        try:
            sources = ContentBudgetCommandOwner._prepare_sources(
                transaction, scope, review_key, before_capacity=True, claimed_token=token)
            approval, _amount = ContentBudgetCommandOwner._approved_action(transaction, scope, sources.task_ref,
                checked_at=sources.snapshot.checked_at, review_key=review_key)
        except (ContentBudgetCommandConflict, AipActionTransitionBlocked) as exc:
            raise ContentCapacityConflict("current first content approval required before capacity") from exc
        current = AipAgentRunService(TransactionBoundConnectFactory(transaction, scope)).get(
            scope, sources.action_context.agent_run_id)
        return current, approval

    def _preflight(self, scope: TenantScope, review_key: str, *, token=None):
        with self._connect_write(scope) as conn:
            return self._admit(HostTransaction(conn), scope, review_key, token=token)[0]

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
            # Recheck under the same transaction that spends the sole attempt.
            try:
                self._admit(HostTransaction(conn), scope, review_key)
            except (ContentCapacityConflict, ContentAgentRunConflict, ValueError):
                return None
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

    def _transition(self, scope: TenantScope, current, review_key: str, token: UUID):
        with self._connect_write(scope) as conn:
            transaction = HostTransaction(conn)
            admitted, approval = self._admit(transaction, scope, review_key, token=token)
            if admitted != current:
                raise ContentCapacityConflict("approved queued AgentRun changed before capacity")
            bound = TransactionBoundConnectFactory(transaction, scope)
            resolver = AipModelRuntimeResolver(AipModelRuntimeStore(bound))
            service = AipAgentRunService(bound, model_resolver=resolver)
            # Existing stores and the capacity gate share the admission locks.
            # Their inner commits are suppressed; only this outer owner commits.
            started = service.transition(
                scope, current.agent_run_id, expected_version=current.version,
                from_status=AgentRunStatus.QUEUED, to_status=AgentRunStatus.RUNNING,
                actor=self.actor, occurred_at=datetime.now(UTC),
            )
            fresh = conn.execute(
                """SELECT e.approval_event_id FROM public.aip_action_approval_event e
                    JOIN public.aip_action_proposal p
                      ON p.org_id=e.org_id AND p.project_id=e.project_id AND p.proposal_id=e.proposal_id
                    WHERE e.org_id=%s AND e.project_id=%s AND e.approval_event_id=%s
                      AND e.decision='approved' AND p.status='approved'
                      AND e.expires_at>clock_timestamp() AND p.expires_at>clock_timestamp()""",
                (*scope.key, approval.resource_id),
            ).fetchone()
            if fresh is None:
                raise ContentCapacityConflict("content approval expired before capacity commit")
            conn.commit()
            return started

    def execute_claim(self, scope: TenantScope, review_key: str, token: UUID) -> dict[str, str]:
        if type(scope) is not TenantScope or type(review_key) is not str or type(token) is not UUID:
            raise ValueError("exact claimed content capacity identity required")
        current = self._preflight(scope, review_key, token=token)
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
        # An exception, including an unknown outer commit, leaves the attempt
        # claimed for read-only reconciliation; never run the transition twice.
        started = self._transition(scope, current, review_key, token)
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

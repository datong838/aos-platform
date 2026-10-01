"""Fail-closed helpers for an exact, approved content budget command."""

from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

from aos_api.aip_budget_reservation_contracts import BudgetExactRef, usage_cost_minor
from aos_api.aip_budget_reservation_store import (
    AipBudgetReservationStore, BudgetReservationError, canonical_hash,
)
from aos_api.tenant_scope import TenantScope
from aos_api.ecommerce_growth_runtime_connection import connect_read_only, connect_serializable
from aos_api.ecommerce_growth_runtime_adapters import (
    ContentGenerateHostService, ReviewAdvanceHostService, TransactionBoundConnectFactory,
    _analysis_command_hash, _request_hash, _strict_content_generate_command,
)
from aos_api.ecommerce_content_agentrun_owner import ContentAgentRunOwner
from aos_api.ecommerce_content_taskrun_owner import ContentTaskRunOwner
from aos_api.aip_agent_run_service import AipAgentRunService
from aos_api.aip_agent_registry_contracts import AgentRunStatus
from aos_api.aip_model_runtime_contracts import ModelRuntimeReadiness
from aos_api.aip_model_runtime_resolver import AipModelRuntimeResolver
from aos_api.aip_model_runtime_store import AipModelRuntimeStore, ModelRuntimeStoreError
from aos_api.aip_model_governance_policy_store import (
    AipModelGovernancePolicyStore, ModelGovernancePolicyStoreError,
)
from aos_api.ecommerce_growth_host_ports import (
    EcommerceGrowthHostError, HostTransaction, LockedEcommerceGrowthHostPort,
)
from aos_api.ecommerce_content_agentrun_owner import ContentAgentRunConflict
from aos_api.ecommerce_content_taskrun_owner import ContentTaskRunConflict


class ContentBudgetCommandConflict(RuntimeError):
    """No unique, current exact authority authorizes content budget use."""


class ContentBudgetCommandOwner:
    """No budget command may infer an approval or silently price an unknown model."""

    def __init__(self, *, connect_read=connect_read_only, connect_write=connect_serializable):
        self._connect_read = connect_read
        self._connect_write = connect_write

    def list_pending(self, scope: TenantScope, *, limit: int = 16) -> list[str]:
        if type(scope) is not TenantScope or type(limit) is not int or not 1 <= limit <= 16:
            raise ValueError("bounded content budget selector and tenant scope required")
        with self._connect_read(scope) as conn:
            rows = conn.execute(
                """SELECT review_key FROM public.ecommerce_growth_content_budget_command_intent
                    WHERE org_id=%s AND project_id=%s AND state='pending' AND attempt=0
                      AND public.ecommerce_growth_content_budget_command_current_a0v_104(
                            org_id,project_id,review_key)
                    ORDER BY created_at,review_key LIMIT %s""",
                (*scope.key, limit),
            ).fetchall()
        keys = [row["review_key"] for row in rows]
        if any(type(key) is not str or not key for key in keys):
            raise ContentBudgetCommandConflict("content budget selector identity drifted")
        return keys

    @staticmethod
    def _command_envelope(
        *, authority_refs: dict[str, dict[str, Any]],
        source_artifact_refs: list[dict[str, Any]],
        fact_source_refs: list[dict[str, Any]],
        approved_fen: int, max_input_tokens: int, max_output_tokens: int,
        review_key: str,
    ) -> dict[str, Any]:
        # The Host cannot import the optional bundle. Its strict parser is
        # authoritative; tests compare this envelope with the bundle contract.
        command = {
            "operation": "content.generate", "authorityRefs": authority_refs,
            "sourceArtifactRefs": source_artifact_refs,
            "factSourceRefs": fact_source_refs, "currency": "CNY",
            "upperBoundFen": approved_fen,
            "maxInputTokens": max_input_tokens,
            "maxOutputTokens": max_output_tokens,
            "idempotencyKey": review_key,
        }
        command["requestHash"] = _analysis_command_hash(command)
        _strict_content_generate_command(command)
        return command

    @classmethod
    def _prepare_sources(
        cls, transaction: HostTransaction, scope: TenantScope, review_key: str,
        *, claimed_token: UUID | None = None,
    ) -> SimpleNamespace:
        """Revalidate sources in the caller's transaction without consuming approval.

        This ephemeral result is not an execution grant and must not be cached
        across transactions. The command path still checks approval and budget.
        """
        if (type(transaction) is not HostTransaction or type(scope) is not TenantScope
                or type(review_key) is not str or not 1 <= len(review_key.strip()) <= 200
                or review_key != review_key.strip()):
            raise ValueError("scoped exact content budget preflight required")
        intent = transaction.execute(
            """SELECT state,attempt,claim_token,task_run_id,agent_run_id,capacity_reservation_id,
                      command_key,installation_id,generation,execution_epoch
                 FROM public.ecommerce_growth_content_budget_command_intent
                WHERE org_id=%s AND project_id=%s AND review_key=%s FOR SHARE""",
            (*scope.key, review_key),
        ).fetchone()
        expected_claim = (
            ("pending", 0, None) if claimed_token is None
            else ("claimed", 1, claimed_token)
        )
        if (intent is None or (intent["state"], intent["attempt"], intent["claim_token"])
                != expected_claim or intent["command_key"] != review_key):
            raise ContentBudgetCommandConflict("pending content budget origin unavailable")
        current = transaction.execute(
            "SELECT public.ecommerce_growth_content_budget_command_current_a0v_104(%s,%s,%s) AS current",
            (*scope.key, review_key),
        ).fetchone()
        if current is None or current["current"] is not True:
            raise ContentBudgetCommandConflict("content budget origin no longer current")
        origin, response = ContentTaskRunOwner._origin(transaction, scope, review_key)
        if ((origin["installation_id"], origin["generation"], origin["execution_epoch"])
                != (intent["installation_id"], intent["generation"], intent["execution_epoch"])):
            raise ContentBudgetCommandConflict("content budget installation lineage drifted")
        dispatch_row = transaction.execute(
            """SELECT handler_kind,revision,installation_id,generation,execution_epoch,
                      cutover_group_id,cutover_group_revision
                 FROM public.extension_operation_dispatch_binding
                WHERE org_id=%s AND project_id=%s
                  AND operation_id='ecommerce_growth_content_generate' FOR SHARE""",
            scope.key,
        ).fetchone()
        if (dispatch_row is None or dispatch_row["handler_kind"] != "extension"
                or (dispatch_row["installation_id"], dispatch_row["generation"],
                    dispatch_row["execution_epoch"], dispatch_row["cutover_group_id"],
                    dispatch_row["cutover_group_revision"])
                != (intent["installation_id"], intent["generation"],
                    intent["execution_epoch"], origin["cutover_group_id"],
                    origin["cutover_group_revision"])):
            raise ContentBudgetCommandConflict("content capability dispatch group drifted")
        dispatch = SimpleNamespace(
            org_id=scope.org_id, project_id=scope.project_id,
            operation_id="ecommerce_growth_content_generate", handler_kind="extension",
            dispatch_revision=dispatch_row["revision"],
            installation_id=intent["installation_id"],
            generation=intent["generation"],
            execution_epoch=intent["execution_epoch"],
            cutover_group_id=origin["cutover_group_id"],
            cutover_group_revision=origin["cutover_group_revision"],
        )
        snapshot = LockedEcommerceGrowthHostPort._lock_and_revalidate(
            transaction, scope, dispatch
        )
        request = ContentAgentRunOwner._build_request(
            transaction, scope, review_key,
            existing_agent_run_id=intent["agent_run_id"],
        )
        if request.task_run_ref.resource_id != intent["task_run_id"]:
            raise ContentBudgetCommandConflict("content TaskRun lineage drifted")
        bound = TransactionBoundConnectFactory(transaction, scope)
        agent = AipAgentRunService(bound).get(scope, intent["agent_run_id"])
        if (agent.status is not AgentRunStatus.RUNNING
                or agent.task_run_id != intent["task_run_id"]
                or agent.request != request.run):
            raise ContentBudgetCommandConflict("running content AgentRun drifted")
        assignment = ContentTaskRunOwner._assignment(transaction, scope)
        if len(assignment["capabilities"]) != 1:
            raise ContentBudgetCommandConflict("one content generation capability required")
        capability = assignment["capabilities"][0]
        checked_at = snapshot.checked_at
        model_store = AipModelRuntimeStore(bound)
        resolution = AipModelRuntimeResolver(model_store).resolve(
            scope, request.run.model_route.asset_id, now=checked_at
        )
        if (resolution.readiness is not ModelRuntimeReadiness.READY
                or resolution.route != request.run.model_route
                or resolution.selected_price_snapshot is None):
            raise ContentBudgetCommandConflict("content route or current price unavailable")
        policy = model_store.get_policy(
            scope, resolution.policy.asset_id, resolution.policy.revision
        )
        governance = AipModelGovernancePolicyStore(bound)
        quota = governance.require_exact_active(
            scope, policy.quota_policy_ref, now=checked_at
        )
        budget_policy = governance.require_exact_active(
            scope, policy.budget_policy_ref, now=checked_at
        )
        price_ref = resolution.selected_price_snapshot
        price = model_store.get_price_snapshot(
            scope, price_ref.asset_id, price_ref.revision
        )
        capacity = transaction.execute(
            """SELECT request_hash,token_units,status,expires_at FROM public.aip_model_capacity_reservation
                WHERE org_id=%s AND project_id=%s AND reservation_id=%s
                  AND agent_run_id=%s FOR SHARE""",
            (*scope.key, intent["capacity_reservation_id"], intent["agent_run_id"]),
        ).fetchone()
        if (capacity is None or capacity["status"] != "reserved"
                or capacity["expires_at"] <= checked_at
                or quota.max_input_tokens + quota.max_output_tokens > capacity["token_units"]):
            raise ContentBudgetCommandConflict("content capacity cannot cover approved token limits")
        task_ref = BudgetExactRef.model_validate(response["taskRef"])
        cost_context = {}
        if price.development_cost_authorization is not None:
            if resolution.selected_model is None or resolution.selected_provider is None:
                raise ContentBudgetCommandConflict("content cost model/provider unavailable")
            model = model_store.get_model(
                scope, resolution.selected_model.asset_id, resolution.selected_model.revision
            )
            if (model.content_hash != resolution.selected_model.content_hash
                    or model.provider != resolution.selected_provider
                    or model.price_snapshot_ref != price_ref):
                raise ContentBudgetCommandConflict("content cost model/provider/price drifted")
            def budget_exact(ref):
                return BudgetExactRef(resource_type=ref.asset_type, resource_id=ref.asset_id,
                    revision=ref.revision, content_hash="sha256:" + ref.content_hash)
            cost_context = dict(transaction=transaction, scope=scope,
                policy_ref=budget_exact(budget_policy.budget_revision_ref),
                pricing_ref=budget_exact(price_ref),
                provider_ref=budget_exact(resolution.selected_provider),
                provider_model_id=model.provider_model_id)
        approved_plan = ReviewAdvanceHostService._revalidate_growth_plan(
            transaction=transaction, scope=scope,
            command={"growthPlanRef": response["growthPlanRef"]},
        )
        method = approved_plan.sales_weapon_method
        if method is None:
            raise ContentBudgetCommandConflict("approved content method unavailable")
        exact = lambda kind, identity, revision, digest: {
            "resourceType": kind, "resourceId": identity, "revision": revision,
            "contentHash": "sha256:" + digest.removeprefix("sha256:"),
        }
        authorities = {
            "handoff": response["handoffRef"], "task": response["taskRef"],
            "brief": response["briefRef"], "growth_plan": response["growthPlanRef"],
            "agent_instance": exact(
                "AgentInstanceRevision", assignment["assignee"].resource_id,
                int(assignment["assignee"].revision), assignment["agent_hash"],
            ),
            "responsibility_plan": assignment["plan_ref"],
            "capability": exact(
                "CapabilityRevision", capability.resource_id,
                capability.revision, capability.content_hash,
            ),
            "model_route": exact(
                "ModelRouteRevision", resolution.route.asset_id,
                resolution.route.revision, resolution.route.content_hash,
            ),
            "budget": exact(
                "BudgetRevision", budget_policy.budget_revision_ref.asset_id,
                budget_policy.budget_revision_ref.revision,
                budget_policy.budget_revision_ref.content_hash,
            ),
            "pricing": exact(
                "ModelPriceSnapshotRevision", price_ref.asset_id,
                price_ref.revision, price_ref.content_hash,
            ),
            "capacity_reservation": exact(
                "CapacityReservation", str(intent["capacity_reservation_id"]),
                1, capacity["request_hash"],
            ),
        }
        return SimpleNamespace(
            dispatch=dispatch, snapshot=snapshot, task_ref=task_ref,
            price=price, quota=quota, cost_context=cost_context, authorities=authorities,
            action_context=SimpleNamespace(request=request, response=response,
                agent_run_id=intent["agent_run_id"], resolution=resolution,
                runtime_policy=policy, budget_policy=budget_policy, capacity=capacity),
            source_artifact_refs=[item["artifactRef"] for item in response["artifactBindings"]],
            fact_source_refs=[exact(
                "EvidenceBundleRevision", item.resource_id, item.revision,
                item.content_hash,
            ) for item in method.evidence_refs],
        )

    @classmethod
    def _build_command(
        cls, transaction: HostTransaction, scope: TenantScope, review_key: str,
        *, claimed_token: UUID | None = None,
    ) -> tuple[SimpleNamespace, dict[str, Any]]:
        sources = cls._prepare_sources(
            transaction, scope, review_key, claimed_token=claimed_token
        )
        approval_ref, approved_fen = cls._approved_action(
            transaction, scope, sources.task_ref, checked_at=sources.snapshot.checked_at
        )
        cls._approved_bound(
            sources.price, approved_fen, max_input_tokens=sources.quota.max_input_tokens,
            max_output_tokens=sources.quota.max_output_tokens, **sources.cost_context,
        )
        command = cls._command_envelope(
            authority_refs={**sources.authorities,
                "approval": approval_ref.model_dump(mode="json", by_alias=True)},
            source_artifact_refs=sources.source_artifact_refs,
            fact_source_refs=sources.fact_source_refs,
            approved_fen=approved_fen,
            max_input_tokens=sources.quota.max_input_tokens,
            max_output_tokens=sources.quota.max_output_tokens,
            review_key=review_key,
        )
        ContentGenerateHostService().revalidate(
            transaction=transaction, scope=scope, dispatch=sources.snapshot, command=command
        )
        return sources.dispatch, command

    def claim(
        self, scope: TenantScope, review_key: str, *, token: UUID | None = None
    ) -> UUID | None:
        if (type(scope) is not TenantScope or type(review_key) is not str
                or not 1 <= len(review_key.strip()) <= 200
                or review_key != review_key.strip()):
            raise ValueError("scoped content budget claim identity required")
        token = uuid4() if token is None else token
        if type(token) is not UUID:
            raise ValueError("content budget claim token must be UUID")
        with self._connect_write(scope) as conn:
            try:
                self._build_command(HostTransaction(conn), scope, review_key)
            except (
                ContentBudgetCommandConflict, ContentAgentRunConflict,
                ContentTaskRunConflict, BudgetReservationError,
                ModelRuntimeStoreError, ModelGovernancePolicyStoreError,
                EcommerceGrowthHostError, ValueError,
            ):
                return None
            claimed = conn.execute(
                "SELECT public.ecommerce_growth_content_budget_command_claim_a0v_104(%s,%s) AS claimed",
                (review_key, token),
            ).fetchone()
            if claimed is None or claimed["claimed"] is not True:
                return None
            conn.commit()
        with self._connect_read(scope) as conn:
            row = conn.execute(
                """SELECT state,attempt,claim_token
                     FROM public.ecommerce_growth_content_budget_command_intent
                    WHERE org_id=%s AND project_id=%s AND review_key=%s""",
                (*scope.key, review_key),
            ).fetchone()
        if row is None or (row["state"], row["attempt"], row["claim_token"]) != (
            "claimed", 1, token
        ):
            raise ContentBudgetCommandConflict("content budget claim readback unknown")
        return token

    def _capability_port(self):
        from aos_api.ecommerce_growth_host_composition import (
            build_ecommerce_growth_host_ports, build_runtime_ecommerce_growth_registry,
        )
        return build_ecommerce_growth_host_ports(
            build_runtime_ecommerce_growth_registry(),
            connect_factory=self._connect_write,
        ).capability_port

    def _committed_readback(
        self, scope: TenantScope, review_key: str, dispatch: SimpleNamespace,
        command: dict[str, Any], receipt: dict[str, Any],
    ) -> UUID:
        with self._connect_read(scope) as conn:
            rows = conn.execute(
                """SELECT b.reservation_id,b.request_hash AS budget_request_hash,
                          b.state AS budget_state,j.budget_request_hash AS journal_budget_hash,
                          j.command_hash,j.command_payload,r.request_hash AS runtime_hash,
                          r.response,r.target_receipt_ref,r.installation_id,r.generation,
                          r.execution_epoch
                     FROM public.aip_budget_reservation b
                     JOIN public.ecommerce_content_execution_command j
                       ON j.org_id=b.org_id AND j.project_id=b.project_id
                      AND j.reservation_id=b.reservation_id
                     JOIN public.ecommerce_growth_runtime_command_receipt r
                       ON r.org_id=b.org_id AND r.project_id=b.project_id
                      AND r.operation_id=b.operation_id AND r.idempotency_key=b.invocation_key
                    WHERE b.org_id=%s AND b.project_id=%s
                      AND b.operation_id='ecommerce_growth_content_generate'
                      AND b.invocation_key=%s LIMIT 2""",
                (*scope.key, review_key),
            ).fetchall()
        if len(rows) != 1:
            raise ContentBudgetCommandConflict("content command commit readback unknown")
        row = rows[0]
        full_hash = _request_hash(command)
        expected_budget_hash = ContentGenerateHostService._budget_request(command).request_hash()
        persisted = row["response"]
        if (
            row["budget_state"] != "held"
            or row["budget_request_hash"] != expected_budget_hash
            or row["journal_budget_hash"] != expected_budget_hash
            or row["command_hash"] != full_hash.removeprefix("sha256:")
            or row["command_payload"] != command
            or row["runtime_hash"] != full_hash
            or row["installation_id"] != dispatch.installation_id
            or row["generation"] != dispatch.generation
            or row["execution_epoch"] != dispatch.execution_epoch
            or type(persisted) is not dict or persisted != receipt
            or persisted.get("state") != "PENDING"
            or persisted.get("budgetState") != "HELD"
            or persisted.get("requestHash") != command["requestHash"]
            or persisted.get("authorityRefs") != command["authorityRefs"]
            or persisted.get("receiptRef") != row["target_receipt_ref"]
            or persisted.get("budgetReservationRef", {}).get("resourceId")
                != str(row["reservation_id"])
            or persisted.get("providerRequestReceiptRef") is not None
            or persisted.get("sideEffects", {}).get("providerInvocationCount") != 0
        ):
            raise ContentBudgetCommandConflict("content HELD/PENDING/Receipt readback drifted")
        return row["reservation_id"]

    def execute_claim(
        self, scope: TenantScope, review_key: str, token: UUID
    ) -> dict[str, str]:
        if type(scope) is not TenantScope or type(review_key) is not str or type(token) is not UUID:
            raise ValueError("exact claimed content budget identity required")
        with self._connect_write(scope) as conn:
            dispatch, command = self._build_command(
                HostTransaction(conn), scope, review_key, claimed_token=token
            )
        # After the sole durable claim, no exception authorizes a second commit.
        # Even a timeout may have committed: leave claimed for read-only reconciliation.
        receipt = self._capability_port().commit(
            dispatch_ref=dispatch, command=command, occurred_at=None
        )
        reservation_id = self._committed_readback(
            scope, review_key, dispatch, command, receipt
        )
        with self._connect_write(scope) as conn:
            ack = conn.execute(
                "SELECT public.ecommerce_growth_content_budget_command_ack_a0v_104(%s,%s,%s) AS accepted",
                (review_key, token, reservation_id),
            ).fetchone()
            if ack is None or ack["accepted"] is not True:
                raise ContentBudgetCommandConflict("content budget ack unavailable")
            conn.commit()
        with self._connect_read(scope) as conn:
            final = conn.execute(
                """SELECT state,attempt,claim_token,budget_reservation_id
                     FROM public.ecommerce_growth_content_budget_command_intent
                    WHERE org_id=%s AND project_id=%s AND review_key=%s""",
                (*scope.key, review_key),
            ).fetchone()
        if final is None or (
            final["state"], final["attempt"], final["claim_token"],
            final["budget_reservation_id"],
        ) != ("accepted", 1, token, reservation_id):
            raise ContentBudgetCommandConflict("content budget accepted readback unknown")
        return {"status": "CONTENT_BUDGET_PENDING", "reviewKey": review_key,
                "budgetReservationId": str(reservation_id)}

    def run_once(self, scope: TenantScope, *, limit: int = 16) -> list[dict[str, str]]:
        results = []
        for review_key in self.list_pending(scope, limit=limit):
            token = self.claim(scope, review_key)
            if token is not None:
                results.append(self.execute_claim(scope, review_key, token))
        return results

    async def serve(self, stop, *, host_ready, interval_seconds: int = 15) -> None:
        if type(interval_seconds) is not int or not 1 <= interval_seconds <= 300:
            raise ValueError("content budget worker interval invalid")
        scope = TenantScope("org-org", "dev-project")
        while not stop.is_set():
            if not host_ready():
                raise RuntimeError("content budget Runtime Host unavailable")
            await asyncio.to_thread(self.run_once, scope)
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
            except TimeoutError:
                pass


    @staticmethod
    def _approved_action(
        transaction: Any, scope: TenantScope, task_ref: BudgetExactRef,
        *, checked_at: datetime,
    ) -> tuple[BudgetExactRef, int]:
        if (type(scope) is not TenantScope or type(task_ref) is not BudgetExactRef
                or task_ref.resource_type != "Task" or type(checked_at) is not datetime
                or checked_at.utcoffset() is None):
            raise ValueError("scoped Task and timezone-aware database cutoff required")
        rows = transaction.execute(
            """SELECT e.approval_event_id,e.proposal_id,e.proposal_version,
                      e.proposal_hash,e.decision,e.actor_id,e.reason,e.expires_at,
                      e.created_at,e.action_binding_hash
                 FROM public.aip_action_approval_event e
                 JOIN public.aip_action_proposal p
                   ON p.org_id=e.org_id AND p.project_id=e.project_id
                  AND p.proposal_id=e.proposal_id
                WHERE e.org_id=%s AND e.project_id=%s AND p.task_id=%s
                  AND p.action_type_id='ecommerce_growth_content_generate'
                  AND p.status='approved' AND e.decision='approved'
                  AND (e.expires_at IS NULL OR e.expires_at>%s)
                  AND (p.expires_at IS NULL OR p.expires_at>%s)
                ORDER BY e.approval_event_id LIMIT 2 FOR SHARE OF e,p""",
            (*scope.key, task_ref.resource_id, checked_at, checked_at),
        ).fetchall()
        if len(rows) != 1:
            raise ContentBudgetCommandConflict("one current content approval required")
        event = rows[0]
        if (event["created_at"] > checked_at or event["decision"] != "approved"
                or event["expires_at"] is not None and event["expires_at"] <= checked_at):
            raise ContentBudgetCommandConflict("content approval expired or future-dated")
        draft = transaction.execute(
            """SELECT proposal_hash,snapshot FROM public.aip_action_draft
                WHERE org_id=%s AND project_id=%s AND proposal_id=%s FOR SHARE""",
            (*scope.key, event["proposal_id"]),
        ).fetchone()
        stable = AipBudgetReservationStore._load(draft["snapshot"]) if draft else None
        payload = stable.get("payload") if type(stable) is dict else None
        amount = payload.get("budgetUpperBoundMinor") if type(payload) is dict else None
        if (draft is None or draft["proposal_hash"] != event["proposal_hash"]
                or type(amount) is not int or not 1 <= amount <= 100_000_000):
            raise ContentBudgetCommandConflict("original approved upper bound unavailable")
        ref = BudgetExactRef(
            resource_type="ActionApprovalEvent", resource_id=event["approval_event_id"],
            revision=event["proposal_version"],
            content_hash=canonical_hash(dict(event), prefixed=True),
        )
        try:
            AipBudgetReservationStore()._approval_authority(
                transaction, scope, ref, checked_at, task_ref=task_ref,
                operation_id="ecommerce_growth_content_generate",
                upper_bound_minor=amount,
            )
        except BudgetReservationError as exc:
            raise ContentBudgetCommandConflict("content approval exact authority drifted") from exc
        return ref, amount

    @staticmethod
    def _minimum_bound_fen(
        price: Any, *, max_input_tokens: int, max_output_tokens: int
    ) -> int:
        if (
            price.development_cost_authorization is not None
            or price.input_token_price is None
            or price.output_token_price is None
            or type(price.token_unit) is not int
            or price.token_unit <= 0
            or type(max_input_tokens) is not int
            or max_input_tokens <= 0
            or type(max_output_tokens) is not int
            or max_output_tokens <= 0
        ):
            raise ValueError("exact numeric price and positive token limits required")
        return usage_cost_minor(
            quantity=max_input_tokens,
            unit_price_cny=str(price.input_token_price),
            price_unit=price.token_unit,
        ) + usage_cost_minor(
            quantity=max_output_tokens,
            unit_price_cny=str(price.output_token_price),
            price_unit=price.token_unit,
        )

    @classmethod
    def _approved_bound(
        cls, price: Any, approved_fen: int, *, max_input_tokens: int, max_output_tokens: int,
        transaction: HostTransaction | None = None, scope: TenantScope | None = None,
        policy_ref: BudgetExactRef | None = None, pricing_ref: BudgetExactRef | None = None,
        provider_ref: BudgetExactRef | None = None, provider_model_id: str | None = None,
    ) -> int:
        if price.development_cost_authorization is not None:
            if (type(transaction) is not HostTransaction or type(scope) is not TenantScope
                    or type(approved_fen) is not int or not 1 <= approved_fen <= 100_000_000
                    or type(max_input_tokens) is not int or max_input_tokens <= 0
                    or type(max_output_tokens) is not int or max_output_tokens <= 0
                    or type(provider_model_id) is not str or not provider_model_id
                    or provider_model_id != provider_model_id.strip()):
                raise ValueError("current scoped cost context and positive bounds required")
            for ref, kind in ((policy_ref, "BudgetRevision"),
                              (pricing_ref, "ModelPriceSnapshotRevision"),
                              (provider_ref, "ProviderInstanceRevision")):
                if type(ref) is not BudgetExactRef or ref.resource_type != kind:
                    raise ValueError("exact content cost references required")
            from aos_api.aip_budget_cost_runtime import require_cost_risk
            verified = require_cost_risk(transaction, scope, policy_ref, pricing_ref,
                                         approved_fen, provider_ref=provider_ref)
            if (verified is None or verified != price
                    or verified.development_cost_authorization.provider_model_id != provider_model_id):
                raise ValueError("content cost price or resolved provider model drifted")
            return approved_fen
        minimum = cls._minimum_bound_fen(
            price, max_input_tokens=max_input_tokens, max_output_tokens=max_output_tokens
        )
        if type(approved_fen) is not int or approved_fen <= 0 or approved_fen < minimum:
            raise ValueError("approved upper bound does not cover maximum priced usage")
        return approved_fen


__all__ = ["ContentBudgetCommandOwner", "ContentBudgetCommandConflict"]

"""Fail-closed helpers for an exact, approved content budget command."""

from __future__ import annotations

from typing import Any
from datetime import datetime

from aos_api.aip_budget_reservation_contracts import BudgetExactRef, usage_cost_minor
from aos_api.aip_budget_reservation_store import (
    AipBudgetReservationStore, BudgetReservationError, canonical_hash,
)
from aos_api.tenant_scope import TenantScope
from aos_api.ecommerce_growth_runtime_connection import connect_read_only, connect_serializable


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
        cls, price: Any, approved_fen: int, *, max_input_tokens: int, max_output_tokens: int
    ) -> int:
        minimum = cls._minimum_bound_fen(
            price, max_input_tokens=max_input_tokens, max_output_tokens=max_output_tokens
        )
        if type(approved_fen) is not int or approved_fen <= 0 or approved_fen < minimum:
            raise ValueError("approved upper bound does not cover maximum priced usage")
        return approved_fen

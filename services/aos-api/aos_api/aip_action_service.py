"""Application service for the AIP-3A proposal and approval gate."""
from __future__ import annotations

from aos_api.aip_action_models import (
    ActionDraftBundle,
    ActionDraftRevisionSnapshot,
    CreateActionDraftRequest,
    CreateActionProposalRequest,
    DecideActionProposalRequest,
    ReviseActionDraftRequest,
    SubmitActionDraftRequest,
    WithdrawActionProposalRequest,
)
from aos_api.aip_action_policy import classify_action_risk
from aos_api.aip_action_store import AipActionStore
from aos_api.auth import Principal
from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.marking import ensure_field_writes, ensure_markings
from aos_api.routers.actions import ensure_action_schema
from aos_api.submission import evaluate_criteria
from aos_api.tenant_scope import TenantScope


class AipActionService:
    def __init__(self, store: AipActionStore) -> None:
        self._store = store

    def create_proposal(
        self,
        principal: Principal,
        idempotency_key: str,
        body: CreateActionProposalRequest,
    ) -> ActionDraftBundle:
        scope = TenantScope(principal.org_id, principal.project_id)
        ensure_action_schema(scope)
        snapshot = self._store.action_type_snapshot(scope, body.action_type_id)
        with connect(scope) as conn:
            ensure_markings(principal, snapshot.get("requiredMarkings") or [], conn=conn)
            props_row = conn.execute(
                "SELECT properties FROM meta_object_type WHERE id=%s",
                (snapshot["objectType"],),
            ).fetchone()
            properties = props_row["properties"] if props_row else None
            if isinstance(properties, list):
                ensure_field_writes(principal, body.payload, properties, conn=conn)
        gate = evaluate_criteria(snapshot.get("submissionCriteria") or [], body.payload)
        if not gate["ok"]:
            raise ApiError(
                code="AIP_INVALID_ARGUMENT",
                message="Action submission criteria not met",
                status_code=400,
                details=gate,
            )
        risk = classify_action_risk(body.action_type_id, snapshot, body.payload, body.risk_hint)
        return self._store.create_proposal(
            scope, principal.subject, idempotency_key, body, snapshot, risk
        )

    def create_draft(
        self,
        principal: Principal,
        idempotency_key: str,
        body: CreateActionDraftRequest,
    ) -> ActionDraftRevisionSnapshot:
        scope, snapshot, risk = self._prepare_action(principal, body)
        return self._store.create_action_draft(
            scope, principal.subject, idempotency_key, body, snapshot, risk
        )

    def revise_draft(
        self,
        principal: Principal,
        draft_id: str,
        idempotency_key: str,
        body: ReviseActionDraftRequest,
    ) -> ActionDraftRevisionSnapshot:
        scope, snapshot, risk = self._prepare_action(principal, body)
        return self._store.revise_action_draft(
            scope,
            principal.subject,
            draft_id,
            idempotency_key,
            body,
            snapshot,
            risk,
        )

    def submit_draft(
        self,
        principal: Principal,
        draft_id: str,
        idempotency_key: str,
        body: SubmitActionDraftRequest,
    ) -> ActionDraftBundle:
        return self._store.submit_action_draft(
            TenantScope(principal.org_id, principal.project_id),
            principal.subject,
            draft_id,
            idempotency_key,
            body,
        )

    def _prepare_action(
        self,
        principal: Principal,
        body: CreateActionDraftRequest | ReviseActionDraftRequest,
    ):
        scope = TenantScope(principal.org_id, principal.project_id)
        ensure_action_schema(scope)
        snapshot = self._store.action_type_snapshot(scope, body.action_type_id)
        with connect(scope) as conn:
            ensure_markings(principal, snapshot.get("requiredMarkings") or [], conn=conn)
            props_row = conn.execute(
                "SELECT properties FROM meta_object_type WHERE id=%s",
                (snapshot["objectType"],),
            ).fetchone()
            properties = props_row["properties"] if props_row else None
            if isinstance(properties, list):
                ensure_field_writes(principal, body.payload, properties, conn=conn)
        gate = evaluate_criteria(snapshot.get("submissionCriteria") or [], body.payload)
        if not gate["ok"]:
            raise ApiError(
                code="AIP_INVALID_ARGUMENT",
                message="Action submission criteria not met",
                status_code=400,
                details=gate,
            )
        risk = classify_action_risk(
            body.action_type_id, snapshot, body.payload, body.risk_hint
        )
        return scope, snapshot, risk

    def decide(
        self,
        principal: Principal,
        proposal_id: str,
        idempotency_key: str,
        body: DecideActionProposalRequest,
    ) -> ActionDraftBundle:
        if not {role.lower() for role in principal.roles}.intersection(
            {"admin", "approver", "aip_approver"}
        ):
            raise ApiError(
                code="AIP_SCOPE_FORBIDDEN",
                message="Action approval role required",
                status_code=403,
            )
        return self._store.decide(
            TenantScope(principal.org_id, principal.project_id),
            principal.subject,
            proposal_id,
            idempotency_key,
            body,
            tuple(principal.roles),
        )

    def withdraw(
        self,
        principal: Principal,
        proposal_id: str,
        idempotency_key: str,
        body: WithdrawActionProposalRequest,
    ) -> ActionDraftBundle:
        return self._store.withdraw(
            TenantScope(principal.org_id, principal.project_id),
            principal.subject,
            proposal_id,
            idempotency_key,
            body,
        )

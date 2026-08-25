"""PostgreSQL authority for AIP Action Proposal, Draft and Approval."""
from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime, timedelta, timezone
from typing import Any

from aos_api.aip_action_models import (
    ActionApprovalEventSnapshot,
    ActionDraftBundle,
    ActionDraftRevisionSnapshot,
    ActionProposalSnapshot,
    ActionProposalTimeline,
    CreateActionDraftRequest,
    CreateActionProposalRequest,
    DecideActionProposalRequest,
    ReviseActionDraftRequest,
    SubmitActionDraftRequest,
    actor,
)
from aos_api.aip_action_policy import RiskDecision
from aos_api.aip_contracts import (
    ActionProposalStatus,
    ActionRiskLevel,
    ActionTypeRevisionRef,
    ApprovalDecision,
    DraftSnapshot,
    ResourceRef,
)
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

ConnectFactory = Callable[..., AbstractContextManager[Any]]

W5_EXTERNAL_ACTION_FAMILIES = frozenset(
    {
        "order.remark",
        "price.alert",
        "creator.invite",
        "customer.service-message",
        "content.publish",
        "campaign.schedule",
        "bulk.contact",
        "creator.contract",
        "price.update",
        "inventory.update",
        "order.fulfill",
        "refund.payment",
    }
)


class AipActionStoreError(RuntimeError):
    code = "AIP_ACTION_STORE_ERROR"


class AipActionNotFound(AipActionStoreError):
    code = "AIP_RESOURCE_NOT_FOUND"


class AipActionConflict(AipActionStoreError):
    code = "AIP_VERSION_CONFLICT"


class AipActionIdempotencyConflict(AipActionStoreError):
    code = "AIP_IDEMPOTENCY_CONFLICT"


class AipActionTransitionBlocked(AipActionStoreError):
    code = "AIP_INVALID_TRANSITION"


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


class AipActionStore:
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def action_type_snapshot(self, scope: TenantScope, action_type_id: str) -> dict[str, Any]:
        with self._connect(scope) as conn:
            row = conn.execute(
                "SELECT id,name,object_type,parameters,required_markings,submission_criteria FROM meta_action_type WHERE id=%s",
                (action_type_id,),
            ).fetchone()
        if row is None:
            raise AipActionNotFound("action type not found")
        snapshot = {
            "id": row["id"], "name": row["name"], "objectType": row["object_type"],
            "parameters": row["parameters"], "requiredMarkings": row["required_markings"],
            "submissionCriteria": row["submission_criteria"],
        }
        snapshot["revisionHash"] = canonical_hash(snapshot)
        return snapshot

    def create_action_draft(
        self,
        scope: TenantScope,
        actor_id: str,
        idempotency_key: str,
        body: CreateActionDraftRequest,
        action_snapshot: dict[str, Any],
        risk: RiskDecision,
    ) -> ActionDraftRevisionSnapshot:
        request = body.model_dump(mode="json", by_alias=True)
        risk_snapshot = self._risk_snapshot(risk)
        approval_policy_hash = canonical_hash(
            {
                "floor": risk_snapshot["floor"],
                "reasons": risk_snapshot["reasons"],
                **risk_snapshot["policy"],
            }
        )
        content_hash = canonical_hash(
            {
                "request": request,
                "actionType": action_snapshot,
                "risk": risk_snapshot,
                "lifecycle": "editable",
            }
        )
        request_hash = canonical_hash(
            {"request": request, "actionTypeRevisionHash": action_snapshot["revisionHash"]}
        )
        draft_id = f"action-draft-{uuid.uuid4().hex[:20]}"
        with self._connect(scope) as conn:
            self._idempotency_lock(conn, scope, "explicit-draft", idempotency_key)
            replay = conn.execute(
                """SELECT draft_id,request_hash FROM aip_action_draft_command
                   WHERE org_id=%s AND project_id=%s AND idempotency_key=%s""",
                (*scope.key, idempotency_key),
            ).fetchone()
            if replay is not None:
                if replay["request_hash"] != request_hash:
                    raise AipActionIdempotencyConflict(
                        "idempotency key reused for different Action Draft"
                    )
                return self._action_draft_revision(conn, scope, replay["draft_id"])
            self._validate_task_run(conn, scope, body.task_id, body.run_id)
            conn.execute(
                """INSERT INTO aip_action_draft_head
                   (org_id,project_id,draft_id,current_revision,version,lifecycle,
                    idempotency_key,request_hash,created_by)
                   VALUES (%s,%s,%s,1,1,'editable',%s,%s,%s)""",
                (*scope.key, draft_id, idempotency_key, request_hash, actor_id),
            )
            self._insert_action_draft_revision(
                conn,
                scope,
                draft_id,
                1,
                "editable",
                request,
                action_snapshot,
                risk_snapshot,
                approval_policy_hash,
                content_hash,
                actor_id,
            )
            conn.execute(
                """INSERT INTO aip_action_draft_command
                   (org_id,project_id,command_id,draft_id,command_kind,request_hash,
                    result_revision,idempotency_key,actor_id)
                   VALUES (%s,%s,%s,%s,'create',%s,1,%s,%s)""",
                (
                    *scope.key,
                    f"draft-command-{uuid.uuid4().hex[:20]}",
                    draft_id,
                    request_hash,
                    idempotency_key,
                    actor_id,
                ),
            )
            conn.commit()
            return self._action_draft_revision(conn, scope, draft_id)

    def revise_action_draft(
        self,
        scope: TenantScope,
        actor_id: str,
        draft_id: str,
        idempotency_key: str,
        body: ReviseActionDraftRequest,
        action_snapshot: dict[str, Any],
        risk: RiskDecision,
    ) -> ActionDraftRevisionSnapshot:
        request = CreateActionDraftRequest.model_validate(
            body.model_dump(mode="python", exclude={"expected_revision", "expected_content_hash"})
        ).model_dump(mode="json", by_alias=True)
        risk_snapshot = self._risk_snapshot(risk)
        approval_policy_hash = canonical_hash(
            {
                "floor": risk_snapshot["floor"],
                "reasons": risk_snapshot["reasons"],
                **risk_snapshot["policy"],
            }
        )
        request_hash = canonical_hash(
            {
                "request": body.model_dump(mode="json", by_alias=True),
                "actionTypeRevisionHash": action_snapshot["revisionHash"],
            }
        )
        with self._connect(scope) as conn:
            self._idempotency_lock(conn, scope, "explicit-draft", idempotency_key)
            replay = conn.execute(
                """SELECT draft_id,request_hash,result_revision FROM aip_action_draft_command
                   WHERE org_id=%s AND project_id=%s AND idempotency_key=%s""",
                (*scope.key, idempotency_key),
            ).fetchone()
            if replay is not None:
                if replay["draft_id"] != draft_id or replay["request_hash"] != request_hash:
                    raise AipActionIdempotencyConflict(
                        "idempotency key reused for different Action Draft revision"
                    )
                return self._action_draft_revision(
                    conn, scope, draft_id, int(replay["result_revision"])
                )
            head = self._lock_action_draft_head(conn, scope, draft_id)
            if head["created_by"] != actor_id:
                raise AipActionTransitionBlocked(
                    "only the Action Draft maker may revise it"
                )
            current = self._action_draft_revision(
                conn, scope, draft_id, int(head["current_revision"])
            )
            if head["lifecycle"] != "editable":
                raise AipActionTransitionBlocked("Action Draft is no longer editable")
            if (
                current.revision != body.expected_revision
                or current.content_hash != body.expected_content_hash
            ):
                raise AipActionConflict("Action Draft revision or hash changed")
            self._validate_task_run(conn, scope, body.task_id, body.run_id)
            revision = current.revision + 1
            content_hash = canonical_hash(
                {
                    "request": request,
                    "actionType": action_snapshot,
                    "risk": risk_snapshot,
                    "lifecycle": "editable",
                }
            )
            self._insert_action_draft_revision(
                conn,
                scope,
                draft_id,
                revision,
                "editable",
                request,
                action_snapshot,
                risk_snapshot,
                approval_policy_hash,
                content_hash,
                actor_id,
            )
            conn.execute(
                """UPDATE aip_action_draft_head
                   SET current_revision=%s,version=version+1,updated_at=NOW()
                   WHERE org_id=%s AND project_id=%s AND draft_id=%s""",
                (revision, *scope.key, draft_id),
            )
            conn.execute(
                """INSERT INTO aip_action_draft_command
                   (org_id,project_id,command_id,draft_id,command_kind,request_hash,
                    result_revision,idempotency_key,actor_id)
                   VALUES (%s,%s,%s,%s,'revise',%s,%s,%s,%s)""",
                (
                    *scope.key,
                    f"draft-command-{uuid.uuid4().hex[:20]}",
                    draft_id,
                    request_hash,
                    revision,
                    idempotency_key,
                    actor_id,
                ),
            )
            conn.commit()
            return self._action_draft_revision(conn, scope, draft_id, revision)

    def submit_action_draft(
        self,
        scope: TenantScope,
        actor_id: str,
        draft_id: str,
        idempotency_key: str,
        body: SubmitActionDraftRequest,
    ) -> ActionDraftBundle:
        request_hash = canonical_hash(body.model_dump(mode="json", by_alias=True))
        with self._connect(scope) as conn:
            self._idempotency_lock(conn, scope, "explicit-draft", idempotency_key)
            replay = conn.execute(
                """SELECT draft_id,request_hash,result_proposal_id
                   FROM aip_action_draft_command
                   WHERE org_id=%s AND project_id=%s AND idempotency_key=%s""",
                (*scope.key, idempotency_key),
            ).fetchone()
            if replay is not None:
                if replay["draft_id"] != draft_id or replay["request_hash"] != request_hash:
                    raise AipActionIdempotencyConflict(
                        "idempotency key reused for different Action Draft submit"
                    )
                return self._bundle(conn, scope, replay["result_proposal_id"])
            head = self._lock_action_draft_head(conn, scope, draft_id)
            if head["created_by"] != actor_id:
                raise AipActionTransitionBlocked(
                    "only the Action Draft maker may submit it"
                )
            current = self._action_draft_revision(
                conn, scope, draft_id, int(head["current_revision"])
            )
            if head["lifecycle"] != "editable":
                raise AipActionTransitionBlocked("Action Draft is no longer submittable")
            if (
                current.revision != body.expected_revision
                or current.content_hash != body.expected_content_hash
            ):
                raise AipActionConflict("Action Draft revision or hash changed before submit")
            request = CreateActionProposalRequest.model_validate(
                current.request.model_dump(mode="python")
            )
            risk_row = conn.execute(
                """SELECT risk_snapshot,action_type_snapshot FROM aip_action_draft_revision
                   WHERE org_id=%s AND project_id=%s AND draft_id=%s AND revision=%s""",
                (*scope.key, draft_id, current.revision),
            ).fetchone()
            risk_data = risk_row["risk_snapshot"]
            risk = RiskDecision(
                level=ActionRiskLevel(risk_data["level"]),
                floor=ActionRiskLevel(risk_data["floor"]),
                reasons=tuple(risk_data["reasons"]),
                approval_policy=dict(risk_data["policy"]),
            )
            if bool(risk.approval_policy.get("draftOnly")):
                raise AipActionTransitionBlocked("ACTION_DRAFT_ONLY_POLICY")
            submitted_revision = current.revision + 1
            submitted_hash = canonical_hash(
                {
                    "previousContentHash": current.content_hash,
                    "lifecycle": "submitted",
                    "submittedBy": actor_id,
                }
            )
            source_draft_ref = {
                "resourceType": "ActionDraftRevision",
                "resourceId": draft_id,
                "revision": submitted_revision,
                "contentHash": submitted_hash,
            }
            stable, action_binding_hash = self._proposal_stable(
                conn,
                scope,
                actor_id,
                request,
                risk_row["action_type_snapshot"],
                risk,
                source_draft_ref=source_draft_ref,
            )
            proposal_id = f"proposal-{uuid.uuid4().hex[:20]}"
            self._insert_action_draft_revision(
                conn,
                scope,
                draft_id,
                submitted_revision,
                "submitted",
                current.request.model_dump(mode="json", by_alias=True),
                risk_row["action_type_snapshot"],
                risk_data,
                current.approval_policy_hash,
                submitted_hash,
                actor_id,
            )
            self._insert_proposal_rows(
                conn,
                scope,
                proposal_id,
                f"action-draft-projection-{uuid.uuid4().hex[:20]}",
                f"action-event-{uuid.uuid4().hex[:20]}",
                actor_id,
                idempotency_key,
                request_hash,
                request,
                risk_row["action_type_snapshot"],
                risk,
                stable,
                action_binding_hash,
                source_draft_ref=source_draft_ref,
            )
            conn.execute(
                """UPDATE aip_action_draft_head SET current_revision=%s,version=version+1,
                   lifecycle='submitted',submitted_proposal_id=%s,updated_at=NOW()
                   WHERE org_id=%s AND project_id=%s AND draft_id=%s""",
                (submitted_revision, proposal_id, *scope.key, draft_id),
            )
            conn.execute(
                """INSERT INTO aip_action_draft_command
                   (org_id,project_id,command_id,draft_id,command_kind,request_hash,
                    result_revision,result_proposal_id,idempotency_key,actor_id)
                   VALUES (%s,%s,%s,%s,'submit',%s,%s,%s,%s,%s)""",
                (
                    *scope.key,
                    f"draft-command-{uuid.uuid4().hex[:20]}",
                    draft_id,
                    request_hash,
                    submitted_revision,
                    proposal_id,
                    idempotency_key,
                    actor_id,
                ),
            )
            conn.commit()
            return self._bundle(conn, scope, proposal_id)

    def create_proposal(
        self,
        scope: TenantScope,
        actor_id: str,
        idempotency_key: str,
        body: CreateActionProposalRequest,
        action_snapshot: dict[str, Any],
        risk: RiskDecision,
    ) -> ActionDraftBundle:
        expires_at = body.effective_expiry()
        if expires_at <= datetime.now(timezone.utc):
            raise AipActionTransitionBlocked("proposal expiry must be in the future")
        request_hash = canonical_hash({
            "request": body.model_dump(mode="json", by_alias=True),
            "actionTypeRevisionHash": action_snapshot["revisionHash"],
            "classifiedRiskLevel": risk.level.value,
            "policy": {"floor": risk.floor.value, "reasons": list(risk.reasons), **risk.approval_policy},
        })
        proposal_id = f"proposal-{uuid.uuid4().hex[:20]}"
        draft_id = f"action-draft-{uuid.uuid4().hex[:20]}"
        event_id = f"action-event-{uuid.uuid4().hex[:20]}"
        with self._connect(scope) as conn:
            self._idempotency_lock(conn, scope, "proposal", idempotency_key)
            replay = conn.execute(
                "SELECT proposal_id,request_hash FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND idempotency_key=%s",
                (*scope.key, idempotency_key),
            ).fetchone()
            if replay is not None:
                if replay["request_hash"] != request_hash:
                    raise AipActionIdempotencyConflict("idempotency key reused for different proposal")
                return self._bundle(conn, scope, replay["proposal_id"])
            self._validate_task_run(conn, scope, body.task_id, body.run_id)
            if (
                body.action_type_id in W5_EXTERNAL_ACTION_FAMILIES
                and body.impact_preview_ref is None
            ):
                raise AipActionTransitionBlocked("EXTERNAL_ACTION_PREVIEW_REQUIRED")
            if body.action_type_id in W5_EXTERNAL_ACTION_FAMILIES:
                raise AipActionTransitionBlocked(
                    "EXTERNAL_ACTION_EXPLICIT_DRAFT_REQUIRED"
                )
            action_binding_hash = None
            if body.impact_preview_ref is not None:
                self.assert_bound_impact_preview_current(
                    conn, scope, body.impact_preview_ref
                )
                from aos_api.aip_production_contract_store import compute_action_binding_hash

                preview_row = conn.execute(
                    """SELECT * FROM aip_impact_preview_revision
                       WHERE org_id=%s AND project_id=%s AND preview_id=%s AND revision=%s""",
                    (
                        *scope.key,
                        body.impact_preview_ref.resource_id,
                        body.impact_preview_ref.revision,
                    ),
                ).fetchone()
                if preview_row is None:
                    raise AipActionTransitionBlocked("impact preview revision not found")
                binding_refs = preview_row["binding_refs"]
                capability_ref = preview_row["capability_ref"]
                account_ref = preview_row["account_ref"]
                external_action_binding = preview_row["external_action_binding"]
                if isinstance(binding_refs, str):
                    binding_refs = json.loads(binding_refs)
                if isinstance(capability_ref, str):
                    capability_ref = json.loads(capability_ref)
                if isinstance(account_ref, str):
                    account_ref = json.loads(account_ref)
                if isinstance(external_action_binding, str):
                    external_action_binding = json.loads(external_action_binding)
                if body.action_type_id in W5_EXTERNAL_ACTION_FAMILIES:
                    if not isinstance(external_action_binding, dict):
                        raise AipActionTransitionBlocked(
                            "EXTERNAL_ACTION_BINDING_REQUIRED"
                        )
                    action_type_ref = external_action_binding.get("actionTypeRef") or {}
                    if (
                        action_type_ref.get("resourceId") != body.action_type_id
                        or action_type_ref.get("contentHash")
                        != action_snapshot["revisionHash"]
                    ):
                        raise AipActionTransitionBlocked(
                            "EXTERNAL_ACTION_TYPE_REVISION_DRIFTED"
                        )
                    if external_action_binding.get("purpose") != body.purpose:
                        raise AipActionTransitionBlocked(
                            "EXTERNAL_ACTION_PURPOSE_DRIFTED"
                        )
                action_binding_hash = compute_action_binding_hash(
                    org_id=scope.org_id,
                    project_id=scope.project_id,
                    preview_id=preview_row["preview_id"],
                    revision=int(preview_row["revision"]),
                    content_hash=preview_row["content_hash"],
                    dependency_snapshot_hash=preview_row["dependency_snapshot_hash"],
                    binding_refs=binding_refs,
                    capability_ref=capability_ref,
                    account_ref=account_ref,
                    external_action_binding=external_action_binding,
                    expires_at=preview_row["expires_at"],
                )
            stable = {
                "tenantScope": {"orgId": scope.org_id, "projectId": scope.project_id},
                "createdBy": actor_id,
                "actionType": action_snapshot,
                "taskId": body.task_id,
                "runId": body.run_id,
                "objectRef": body.object_ref.model_dump(mode="json", by_alias=True) if body.object_ref else None,
                "purpose": body.purpose,
                "riskLevel": risk.level.value,
                "policy": {"floor": risk.floor.value, "reasons": list(risk.reasons), **risk.approval_policy},
                "approvalPolicyHash": canonical_hash(
                    {
                        "floor": risk.floor.value,
                        "reasons": list(risk.reasons),
                        **risk.approval_policy,
                    }
                ),
                "payload": body.payload,
                "diff": body.diff,
                "evidenceRefs": [item.model_dump(mode="json", by_alias=True) for item in body.evidence_refs],
                "impactPreviewRef": (
                    body.impact_preview_ref.model_dump(mode="json", by_alias=True)
                    if body.impact_preview_ref
                    else None
                ),
                "actionBindingHash": action_binding_hash,
                "expiresAt": expires_at.isoformat(),
            }
            policy = stable["policy"]
            proposal_hash = canonical_hash(stable)
            conn.execute(
                """INSERT INTO aip_action_proposal (
                   org_id,project_id,proposal_id,action_type_id,action_type_revision_hash,
                   action_type_snapshot,task_id,run_id,object_ref,purpose,client_risk_hint,risk_level,
                   policy_snapshot,payload,diff,evidence_refs,impact_preview_id,
                   impact_preview_revision,impact_preview_hash,action_binding_hash,approval_policy_hash,
                   proposal_hash,status,expires_at,
                   idempotency_key,request_hash,version,created_by,created_at,updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s::jsonb,%s,%s,%s,%s::jsonb,
                           %s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s,'drafted',%s,%s,%s,1,%s,NOW(),NOW())""",
                (*scope.key, proposal_id, body.action_type_id, action_snapshot["revisionHash"],
                 self._json(action_snapshot), body.task_id, body.run_id, self._json(stable["objectRef"]),
                 body.purpose, body.risk_hint.value if body.risk_hint else None, risk.level.value,
                 self._json(policy), self._json(body.payload), self._json(body.diff),
                 self._json(stable["evidenceRefs"]),
                 body.impact_preview_ref.resource_id if body.impact_preview_ref else None,
                 body.impact_preview_ref.revision if body.impact_preview_ref else None,
                 body.impact_preview_ref.content_hash if body.impact_preview_ref else None,
                 action_binding_hash, stable["approvalPolicyHash"], proposal_hash,
                 expires_at, idempotency_key,
                 request_hash, actor_id),
            )
            conn.execute(
                """INSERT INTO aip_action_draft (
                   org_id,project_id,draft_id,proposal_id,proposal_version,proposal_hash,snapshot,diff,
                   evidence_refs,approval_policy,status,created_by,created_at,updated_at)
                   VALUES (%s,%s,%s,%s,1,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
                           'awaiting_approval',%s,NOW(),NOW())""",
                (*scope.key, draft_id, proposal_id, proposal_hash, self._json(stable),
                 self._json(body.diff), self._json(stable["evidenceRefs"]), self._json(policy), actor_id),
            )
            conn.execute(
                """INSERT INTO aip_action_event
                   (org_id,project_id,event_id,proposal_id,event_type,actor_id,proposal_version,proposal_hash,payload)
                   VALUES (%s,%s,%s,%s,'drafted',%s,1,%s,%s::jsonb)""",
                (*scope.key, event_id, proposal_id, actor_id, proposal_hash, self._json({"draftId": draft_id})),
            )
            conn.commit()
            return self._bundle(conn, scope, proposal_id)

    def _proposal_stable(
        self,
        conn: Any,
        scope: TenantScope,
        actor_id: str,
        body: CreateActionProposalRequest,
        action_snapshot: dict[str, Any],
        risk: RiskDecision,
        *,
        source_draft_ref: dict[str, Any] | None,
    ) -> tuple[dict[str, Any], str | None]:
        expires_at = body.effective_expiry()
        if expires_at <= datetime.now(timezone.utc):
            raise AipActionTransitionBlocked("proposal expiry must be in the future")
        self._validate_task_run(conn, scope, body.task_id, body.run_id)
        if (
            body.action_type_id in W5_EXTERNAL_ACTION_FAMILIES
            and body.impact_preview_ref is None
        ):
            raise AipActionTransitionBlocked("EXTERNAL_ACTION_PREVIEW_REQUIRED")
        action_binding_hash = None
        if body.impact_preview_ref is not None:
            self.assert_bound_impact_preview_current(conn, scope, body.impact_preview_ref)
            from aos_api.aip_production_contract_store import compute_action_binding_hash

            preview_row = conn.execute(
                """SELECT * FROM aip_impact_preview_revision
                   WHERE org_id=%s AND project_id=%s AND preview_id=%s AND revision=%s""",
                (
                    *scope.key,
                    body.impact_preview_ref.resource_id,
                    body.impact_preview_ref.revision,
                ),
            ).fetchone()
            if preview_row is None:
                raise AipActionTransitionBlocked("impact preview revision not found")
            values = {
                "binding_refs": preview_row["binding_refs"],
                "capability_ref": preview_row["capability_ref"],
                "account_ref": preview_row["account_ref"],
                "external_action_binding": preview_row["external_action_binding"],
            }
            for key, value in values.items():
                if isinstance(value, str):
                    values[key] = json.loads(value)
            external = values["external_action_binding"]
            if body.action_type_id in W5_EXTERNAL_ACTION_FAMILIES:
                if not isinstance(external, dict):
                    raise AipActionTransitionBlocked("EXTERNAL_ACTION_BINDING_REQUIRED")
                action_type_ref = external.get("actionTypeRef") or {}
                if (
                    action_type_ref.get("resourceId") != body.action_type_id
                    or action_type_ref.get("contentHash")
                    != action_snapshot["revisionHash"]
                ):
                    raise AipActionTransitionBlocked(
                        "EXTERNAL_ACTION_TYPE_REVISION_DRIFTED"
                    )
                if external.get("purpose") != body.purpose:
                    raise AipActionTransitionBlocked("EXTERNAL_ACTION_PURPOSE_DRIFTED")
            action_binding_hash = compute_action_binding_hash(
                org_id=scope.org_id,
                project_id=scope.project_id,
                preview_id=preview_row["preview_id"],
                revision=int(preview_row["revision"]),
                content_hash=preview_row["content_hash"],
                dependency_snapshot_hash=preview_row["dependency_snapshot_hash"],
                binding_refs=values["binding_refs"],
                capability_ref=values["capability_ref"],
                account_ref=values["account_ref"],
                external_action_binding=external,
                expires_at=preview_row["expires_at"],
            )
        policy = {
            "floor": risk.floor.value,
            "reasons": list(risk.reasons),
            **risk.approval_policy,
        }
        return (
            {
                "tenantScope": {
                    "orgId": scope.org_id,
                    "projectId": scope.project_id,
                },
                "createdBy": actor_id,
                "actionType": action_snapshot,
                "taskId": body.task_id,
                "runId": body.run_id,
                "objectRef": (
                    body.object_ref.model_dump(mode="json", by_alias=True)
                    if body.object_ref
                    else None
                ),
                "purpose": body.purpose,
                "riskLevel": risk.level.value,
                "policy": policy,
                "approvalPolicyHash": canonical_hash(policy),
                "payload": body.payload,
                "diff": body.diff,
                "evidenceRefs": [
                    item.model_dump(mode="json", by_alias=True)
                    for item in body.evidence_refs
                ],
                "impactPreviewRef": (
                    body.impact_preview_ref.model_dump(mode="json", by_alias=True)
                    if body.impact_preview_ref
                    else None
                ),
                "actionBindingHash": action_binding_hash,
                "sourceDraftRef": source_draft_ref,
                "expiresAt": expires_at.isoformat(),
            },
            action_binding_hash,
        )

    def _insert_proposal_rows(
        self,
        conn: Any,
        scope: TenantScope,
        proposal_id: str,
        draft_id: str,
        event_id: str,
        actor_id: str,
        idempotency_key: str,
        request_hash: str,
        body: CreateActionProposalRequest,
        action_snapshot: dict[str, Any],
        risk: RiskDecision,
        stable: dict[str, Any],
        action_binding_hash: str | None,
        *,
        source_draft_ref: dict[str, Any] | None,
    ) -> None:
        policy = stable["policy"]
        proposal_hash = canonical_hash(stable)
        source = source_draft_ref or {}
        conn.execute(
            """INSERT INTO aip_action_proposal (
               org_id,project_id,proposal_id,action_type_id,action_type_revision_hash,
               action_type_snapshot,task_id,run_id,object_ref,purpose,client_risk_hint,risk_level,
               policy_snapshot,payload,diff,evidence_refs,impact_preview_id,
               impact_preview_revision,impact_preview_hash,action_binding_hash,
               source_draft_id,source_draft_revision,source_draft_hash,approval_policy_hash,
               proposal_hash,status,expires_at,idempotency_key,request_hash,version,created_by,
               created_at,updated_at)
               VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s::jsonb,%s,%s,%s,%s::jsonb,
                       %s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                       'drafted',%s,%s,%s,1,%s,NOW(),NOW())""",
            (
                *scope.key,
                proposal_id,
                body.action_type_id,
                action_snapshot["revisionHash"],
                self._json(action_snapshot),
                body.task_id,
                body.run_id,
                self._json(stable["objectRef"]),
                body.purpose,
                body.risk_hint.value if body.risk_hint else None,
                risk.level.value,
                self._json(policy),
                self._json(body.payload),
                self._json(body.diff),
                self._json(stable["evidenceRefs"]),
                body.impact_preview_ref.resource_id if body.impact_preview_ref else None,
                body.impact_preview_ref.revision if body.impact_preview_ref else None,
                body.impact_preview_ref.content_hash if body.impact_preview_ref else None,
                action_binding_hash,
                source.get("resourceId"),
                source.get("revision"),
                source.get("contentHash"),
                stable["approvalPolicyHash"],
                proposal_hash,
                datetime.fromisoformat(stable["expiresAt"]),
                idempotency_key,
                request_hash,
                actor_id,
            ),
        )
        conn.execute(
            """INSERT INTO aip_action_draft (
               org_id,project_id,draft_id,proposal_id,proposal_version,proposal_hash,snapshot,diff,
               evidence_refs,approval_policy,status,created_by,created_at,updated_at)
               VALUES (%s,%s,%s,%s,1,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
                       'awaiting_approval',%s,NOW(),NOW())""",
            (
                *scope.key,
                draft_id,
                proposal_id,
                proposal_hash,
                self._json(stable),
                self._json(body.diff),
                self._json(stable["evidenceRefs"]),
                self._json(policy),
                actor_id,
            ),
        )
        conn.execute(
            """INSERT INTO aip_action_event
               (org_id,project_id,event_id,proposal_id,event_type,actor_id,
                proposal_version,proposal_hash,payload)
               VALUES (%s,%s,%s,%s,'submitted',%s,1,%s,%s::jsonb)""",
            (
                *scope.key,
                event_id,
                proposal_id,
                actor_id,
                proposal_hash,
                self._json({"sourceDraftRef": source_draft_ref}),
            ),
        )

    @staticmethod
    def _risk_snapshot(risk: RiskDecision) -> dict[str, Any]:
        return {
            "level": risk.level.value,
            "floor": risk.floor.value,
            "reasons": list(risk.reasons),
            "policy": dict(risk.approval_policy),
        }

    def _insert_action_draft_revision(
        self,
        conn: Any,
        scope: TenantScope,
        draft_id: str,
        revision: int,
        lifecycle: str,
        request: dict[str, Any],
        action_snapshot: dict[str, Any],
        risk_snapshot: dict[str, Any],
        approval_policy_hash: str,
        content_hash: str,
        actor_id: str,
    ) -> None:
        conn.execute(
            """INSERT INTO aip_action_draft_revision
               (org_id,project_id,draft_id,revision,lifecycle,request_payload,
                action_type_snapshot,risk_snapshot,approval_policy_hash,content_hash,created_by)
               VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s)""",
            (
                *scope.key,
                draft_id,
                revision,
                lifecycle,
                self._json(request),
                self._json(action_snapshot),
                self._json(risk_snapshot),
                approval_policy_hash,
                content_hash,
                actor_id,
            ),
        )

    def _lock_action_draft_head(
        self, conn: Any, scope: TenantScope, draft_id: str
    ) -> Any:
        row = conn.execute(
            """SELECT * FROM aip_action_draft_head
               WHERE org_id=%s AND project_id=%s AND draft_id=%s FOR UPDATE""",
            (*scope.key, draft_id),
        ).fetchone()
        if row is None:
            raise AipActionNotFound("Action Draft not found in scope")
        return row

    def _action_draft_revision(
        self,
        conn: Any,
        scope: TenantScope,
        draft_id: str,
        revision: int | None = None,
    ) -> ActionDraftRevisionSnapshot:
        head = conn.execute(
            """SELECT * FROM aip_action_draft_head
               WHERE org_id=%s AND project_id=%s AND draft_id=%s""",
            (*scope.key, draft_id),
        ).fetchone()
        if head is None:
            raise AipActionNotFound("Action Draft not found in scope")
        selected = revision or int(head["current_revision"])
        row = conn.execute(
            """SELECT * FROM aip_action_draft_revision
               WHERE org_id=%s AND project_id=%s AND draft_id=%s AND revision=%s""",
            (*scope.key, draft_id, selected),
        ).fetchone()
        if row is None:
            raise AipActionNotFound("Action Draft revision not found in scope")
        action = row["action_type_snapshot"]
        risk = row["risk_snapshot"]
        return ActionDraftRevisionSnapshot(
            draft_id=draft_id,
            revision=int(row["revision"]),
            version=int(head["version"]),
            lifecycle=row["lifecycle"],
            request=CreateActionDraftRequest.model_validate(row["request_payload"]),
            action_type_revision_hash=action["revisionHash"],
            risk_level=ActionRiskLevel(risk["level"]),
            approval_policy_hash=row["approval_policy_hash"],
            content_hash=row["content_hash"],
            submitted_proposal_id=head["submitted_proposal_id"],
            created_by=actor(row["created_by"]),
            created_at=row["created_at"],
        )

    def list_proposals(self, scope: TenantScope, limit: int = 100) -> list[ActionDraftBundle]:
        with self._connect(scope) as conn:
            rows = conn.execute(
                "SELECT proposal_id FROM aip_action_proposal WHERE org_id=%s AND project_id=%s ORDER BY updated_at DESC,proposal_id DESC LIMIT %s",
                (*scope.key, limit),
            ).fetchall()
            return [self._bundle(conn, scope, row["proposal_id"]) for row in rows]

    def get_proposal(self, scope: TenantScope, proposal_id: str) -> ActionDraftBundle:
        with self._connect(scope) as conn:
            return self._bundle(conn, scope, proposal_id)

    def decide(
        self,
        scope: TenantScope,
        actor_id: str,
        proposal_id: str,
        idempotency_key: str,
        body: DecideActionProposalRequest,
        actor_roles: tuple[str, ...] = (),
    ) -> ActionDraftBundle:
        request_hash = canonical_hash(body.model_dump(mode="json", by_alias=True))
        with self._connect(scope) as conn:
            self._idempotency_lock(conn, scope, "approval", idempotency_key)
            row = conn.execute(
                "SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s FOR UPDATE",
                (*scope.key, proposal_id),
            ).fetchone()
            if row is None:
                raise AipActionNotFound("proposal not found in scope")
            replay = conn.execute(
                "SELECT proposal_id,request_hash FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND idempotency_key=%s",
                (*scope.key, idempotency_key),
            ).fetchone()
            if replay is not None:
                if replay["request_hash"] != request_hash or replay["proposal_id"] != proposal_id:
                    raise AipActionIdempotencyConflict("idempotency key reused for different approval")
                return self._bundle(conn, scope, proposal_id)
            if row["created_by"] == actor_id:
                raise AipActionTransitionBlocked("maker cannot approve or reject own proposal")
            if row["status"] not in {"drafted", "approved"}:
                raise AipActionTransitionBlocked(f"proposal is not reviewable while {row['status']}")
            if row["expires_at"] <= datetime.now(timezone.utc):
                conn.execute("UPDATE aip_action_proposal SET status='expired',version=version+1,updated_at=NOW() WHERE org_id=%s AND project_id=%s AND proposal_id=%s", (*scope.key, proposal_id))
                conn.execute("UPDATE aip_action_draft SET status='expired',updated_at=NOW() WHERE org_id=%s AND project_id=%s AND proposal_id=%s", (*scope.key, proposal_id))
                conn.commit()
                raise AipActionTransitionBlocked("proposal expired")
            if int(row["version"]) != body.expected_proposal_version or row["proposal_hash"] != body.expected_proposal_hash:
                raise AipActionConflict("proposal revision or hash changed before decision")
            self.assert_bound_impact_preview_current(conn, scope, row)
            policy = row["policy_snapshot"] or {}
            expected_policy_hash = canonical_hash(policy)
            if row["approval_policy_hash"] not in {None, expected_policy_hash}:
                raise AipActionTransitionBlocked("APPROVAL_POLICY_HASH_DRIFTED")
            if row["source_draft_id"] is not None and bool(policy.get("draftOnly")):
                raise AipActionTransitionBlocked("ACTION_DRAFT_ONLY_POLICY")
            if conn.execute(
                "SELECT 1 FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND proposal_id=%s AND actor_id=%s AND decision='approved'",
                (*scope.key, proposal_id, actor_id),
            ).fetchone():
                raise AipActionTransitionBlocked("actor already approved this proposal")
            event_id = f"approval-{uuid.uuid4().hex[:20]}"
            approval_rows = conn.execute(
                """SELECT approval_event_id,actor_id,slot_id FROM aip_action_approval_event
                   WHERE org_id=%s AND project_id=%s AND proposal_id=%s
                     AND decision='approved' ORDER BY created_at,approval_event_id""",
                (*scope.key, proposal_id),
            ).fetchall()
            slot_id = f"checker.{len(approval_rows) + 1}"
            eligibility_snapshot_hash = canonical_hash(
                {
                    "tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
                    "actorId": actor_id,
                    "roles": sorted(role.lower() for role in actor_roles),
                    "slotId": slot_id,
                    "approvalPolicyHash": expected_policy_hash,
                }
            )
            now = datetime.now(timezone.utc)
            max_seconds = int(policy.get("maxApprovalSeconds", 900))
            policy_expiry = min(row["expires_at"], now + timedelta(seconds=max_seconds))
            if body.approval_expires_at is not None:
                if body.approval_expires_at <= now:
                    raise AipActionTransitionBlocked("approval expiry must be in the future")
                approval_expiry = min(policy_expiry, body.approval_expires_at)
            else:
                approval_expiry = policy_expiry
            conn.execute(
                """INSERT INTO aip_action_approval_event
                   (org_id,project_id,approval_event_id,proposal_id,proposal_version,proposal_hash,
                    decision,actor_id,reason,expires_at,idempotency_key,request_hash,
                    action_binding_hash,approval_policy_hash,slot_id,eligibility_snapshot_hash)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (*scope.key, event_id, proposal_id, row["version"], row["proposal_hash"],
                 body.decision.value, actor_id, body.reason, approval_expiry,
                 idempotency_key, request_hash, row["action_binding_hash"],
                 expected_policy_hash, slot_id, eligibility_snapshot_hash),
            )
            next_status = "rejected"
            if body.decision is ApprovalDecision.APPROVED:
                approvals = int(conn.execute(
                    "SELECT COUNT(*) AS n FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND proposal_id=%s AND decision='approved'",
                    (*scope.key, proposal_id),
                ).fetchone()["n"])
                minimum = int(policy.get("minimumApprovals", 1))
                next_status = "approved" if approvals >= minimum else "drafted"
            conn.execute(
                "UPDATE aip_action_proposal SET status=%s,version=version+1,updated_at=NOW() WHERE org_id=%s AND project_id=%s AND proposal_id=%s AND version=%s",
                (next_status, *scope.key, proposal_id, row["version"]),
            )
            conn.execute(
                "UPDATE aip_action_draft SET status=%s,updated_at=NOW() WHERE org_id=%s AND project_id=%s AND proposal_id=%s",
                ("awaiting_approval" if next_status == "drafted" else next_status, *scope.key, proposal_id),
            )
            conn.execute(
                """INSERT INTO aip_action_event
                   (org_id,project_id,event_id,proposal_id,event_type,actor_id,proposal_version,proposal_hash,payload)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",
                (*scope.key, f"action-event-{uuid.uuid4().hex[:20]}", proposal_id,
                 body.decision.value, actor_id, int(row["version"]) + 1, row["proposal_hash"],
                 self._json({"reason": body.reason, "status": next_status})),
            )
            conn.commit()
            return self._bundle(conn, scope, proposal_id)

    def timeline(self, scope: TenantScope, proposal_id: str) -> ActionProposalTimeline:
        with self._connect(scope) as conn:
            bundle = self._bundle(conn, scope, proposal_id)
            rows = conn.execute(
                "SELECT event_id,event_type,actor_id,proposal_version,proposal_hash,payload,created_at FROM aip_action_event WHERE org_id=%s AND project_id=%s AND proposal_id=%s ORDER BY created_at,event_id",
                (*scope.key, proposal_id),
            ).fetchall()
        return ActionProposalTimeline(bundle=bundle, events=[dict(row) for row in rows])

    def _bundle(self, conn: Any, scope: TenantScope, proposal_id: str) -> ActionDraftBundle:
        row = conn.execute("SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s", (*scope.key, proposal_id)).fetchone()
        if row is None:
            raise AipActionNotFound("proposal not found in scope")
        draft = conn.execute("SELECT * FROM aip_action_draft WHERE org_id=%s AND project_id=%s AND proposal_id=%s", (*scope.key, proposal_id)).fetchone()
        approvals = conn.execute("SELECT * FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND proposal_id=%s ORDER BY created_at,approval_event_id", (*scope.key, proposal_id)).fetchall()
        action = row["action_type_snapshot"]
        proposal = ActionProposalSnapshot(
            id=row["proposal_id"],
            action_type=ActionTypeRevisionRef(action_type_id=row["action_type_id"], revision_hash=row["action_type_revision_hash"], object_type=action["objectType"]),
            task_id=row["task_id"], run_id=row["run_id"],
            object_ref=ResourceRef.model_validate(row["object_ref"]) if row["object_ref"] else None,
            purpose=row["purpose"], risk_level=ActionRiskLevel(row["risk_level"]),
            client_risk_hint=ActionRiskLevel(row["client_risk_hint"]) if row["client_risk_hint"] else None,
            policy_snapshot=row["policy_snapshot"], payload=row["payload"], diff=row["diff"],
            evidence_refs=[ResourceRef.model_validate(item) for item in row["evidence_refs"]],
            impact_preview_ref=(
                None
                if row["impact_preview_id"] is None
                else {
                    "resourceType": "ImpactPreviewRevision",
                    "resourceId": row["impact_preview_id"],
                    "revision": int(row["impact_preview_revision"]),
                    "contentHash": row["impact_preview_hash"],
                }
            ),
            action_binding_hash=row["action_binding_hash"],
            approval_policy_hash=row["approval_policy_hash"],
            source_draft_ref=(
                None
                if row["source_draft_id"] is None
                else {
                    "resourceType": "ActionDraftRevision",
                    "resourceId": row["source_draft_id"],
                    "revision": int(row["source_draft_revision"]),
                    "contentHash": row["source_draft_hash"],
                }
            ),
            proposal_hash=row["proposal_hash"], status=ActionProposalStatus(row["status"]),
            expires_at=row["expires_at"], version=row["version"], created_by=actor(row["created_by"]),
            created_at=row["created_at"], updated_at=row["updated_at"],
        )
        draft_model = DraftSnapshot(
            id=draft["draft_id"], proposal_id=proposal_id, proposal_version=draft["proposal_version"],
            proposal_hash=draft["proposal_hash"], diff=draft["diff"],
            evidence_refs=[ResourceRef.model_validate(item) for item in draft["evidence_refs"]],
            status=draft["status"], created_at=draft["created_at"],
        )
        approval_models = [ActionApprovalEventSnapshot(
            id=item["approval_event_id"], proposal_id=proposal_id,
            proposal_version=item["proposal_version"], proposal_hash=item["proposal_hash"],
            decision=ApprovalDecision(item["decision"]), actor=actor(item["actor_id"]),
            reason=item["reason"], expires_at=item["expires_at"], created_at=item["created_at"],
            action_binding_hash=item["action_binding_hash"],
            approval_policy_hash=item["approval_policy_hash"],
            slot_id=item["slot_id"],
            eligibility_snapshot_hash=item["eligibility_snapshot_hash"],
        ) for item in approvals]
        return ActionDraftBundle(proposal=proposal, draft=draft_model, approvals=approval_models)

    @staticmethod
    def _validate_task_run(conn: Any, scope: TenantScope, task_id: str | None, run_id: str | None) -> None:
        if task_id and conn.execute("SELECT 1 FROM aip_task WHERE org_id=%s AND project_id=%s AND task_id=%s", (*scope.key, task_id)).fetchone() is None:
            raise AipActionNotFound("task not found in scope")
        if run_id:
            row = conn.execute("SELECT task_id FROM aip_task_run WHERE org_id=%s AND project_id=%s AND run_id=%s", (*scope.key, run_id)).fetchone()
            if row is None or row["task_id"] != task_id:
                raise AipActionNotFound("run not found for task in scope")

    @staticmethod
    def assert_bound_impact_preview_current(
        conn: Any,
        scope: TenantScope,
        proposal_or_ref: Any,
    ) -> None:
        from aos_api.aip_production_contract_store import (
            AipProductionContractStore,
            ProductionContractDependencyBlocked,
            compute_action_binding_hash,
        )
        from aos_api.aip_production_contracts import ExactRevisionRef

        if isinstance(proposal_or_ref, ExactRevisionRef):
            ref = proposal_or_ref
        else:
            if proposal_or_ref["impact_preview_id"] is None:
                return
            ref = ExactRevisionRef(
                resource_type="ImpactPreviewRevision",
                resource_id=proposal_or_ref["impact_preview_id"],
                revision=int(proposal_or_ref["impact_preview_revision"]),
                content_hash=proposal_or_ref["impact_preview_hash"],
            )
        try:
            preview_row = AipProductionContractStore().assert_frozen_preview_current(
                conn, scope, ref
            )
        except ProductionContractDependencyBlocked as exc:
            raise AipActionTransitionBlocked(str(exc)) from exc
        if not isinstance(proposal_or_ref, ExactRevisionRef):
            external_action_binding = preview_row["external_action_binding"]
            binding_refs = preview_row["binding_refs"]
            capability_ref = preview_row["capability_ref"]
            account_ref = preview_row["account_ref"]
            for name, value in (
                ("external_action_binding", external_action_binding),
                ("binding_refs", binding_refs),
                ("capability_ref", capability_ref),
                ("account_ref", account_ref),
            ):
                if isinstance(value, str):
                    parsed = json.loads(value)
                    if name == "external_action_binding":
                        external_action_binding = parsed
                    elif name == "binding_refs":
                        binding_refs = parsed
                    elif name == "capability_ref":
                        capability_ref = parsed
                    else:
                        account_ref = parsed
            expected_binding_hash = compute_action_binding_hash(
                org_id=scope.org_id,
                project_id=scope.project_id,
                preview_id=preview_row["preview_id"],
                revision=int(preview_row["revision"]),
                content_hash=preview_row["content_hash"],
                dependency_snapshot_hash=preview_row["dependency_snapshot_hash"],
                binding_refs=binding_refs,
                capability_ref=capability_ref,
                account_ref=account_ref,
                external_action_binding=external_action_binding,
                expires_at=preview_row["expires_at"],
            )
            if proposal_or_ref["action_binding_hash"] != expected_binding_hash:
                raise AipActionTransitionBlocked("ACTION_BINDING_HASH_DRIFTED")

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

    def _connect(self, scope: TenantScope):
        try:
            return self._connect_factory(scope)
        except TypeError:
            return self._connect_factory()

    @staticmethod
    def _idempotency_lock(
        conn: Any,
        scope: TenantScope,
        namespace: str,
        idempotency_key: str,
    ) -> None:
        lock_key = f"aip-action:{namespace}:{scope.org_id}:{scope.project_id}:{idempotency_key}"
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (lock_key,))

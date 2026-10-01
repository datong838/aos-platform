"""Bind a persisted first Model Eval application to the original maker/checker Action."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aos_api.aip_action_models import (
    CreateActionProposalRequest, DecideActionProposalRequest,
)
from aos_api.aip_action_policy import RiskDecision, classify_action_risk
from aos_api.aip_action_store import (
    AipActionStore, AipActionTransitionBlocked, canonical_hash,
)
from aos_api.aip_contracts import ActionRiskLevel
from aos_api.aip_model_eval_authorization import ModelEvalRequestCreate
from aos_api.aip_model_eval_request_store import (
    AipModelEvalRequestStore, ModelEvalRequestBlocked,
)
from aos_api.auth import Principal
from aos_api.db import connect as db_connect
from aos_api.openfga import openfga_api_url
from aos_api.tenant_scope import TenantScope

ACTION_ID = "aip_request_model_eval"
OBJECT_ID = "ModelEvalRequest"
_OBJECT = {"id": OBJECT_ID, "name": "模型首次评测申请",
           "description": "仅供独立审批的不可执行申请", "published": True,
           "properties": [], "required_markings": []}
_ACTION = {"id": ACTION_ID, "name": "申请模型首次评测",
           "objectType": OBJECT_ID, "parameters": [], "requiredMarkings": [],
           "submissionCriteria": []}


class ModelEvalActionBlocked(AipActionTransitionBlocked):
    code = "MODEL_EVAL_ACTION_BLOCKED"


class ModelEvalActionGuard:
    """Recheck the immutable application and current dependencies in Action's transaction."""

    @staticmethod
    def read_metadata(conn: Any) -> dict[str, Any]:
        obj = conn.execute("""SELECT id,name,description,published,properties,required_markings
            FROM meta_object_type WHERE id=%s FOR SHARE""", (OBJECT_ID,)).fetchone()
        if obj is None or dict(obj) != _OBJECT:
            raise ModelEvalActionBlocked("MODEL_EVAL_OBJECT_TYPE_DRIFTED")
        row = conn.execute("""SELECT id,name,object_type,parameters,required_markings,
            submission_criteria FROM meta_action_type WHERE id=%s FOR SHARE""",
            (ACTION_ID,)).fetchone()
        if row is None:
            raise ModelEvalActionBlocked("MODEL_EVAL_ACTION_TYPE_MISSING")
        snapshot = {"id": row["id"], "name": row["name"],
                    "objectType": row["object_type"], "parameters": row["parameters"],
                    "requiredMarkings": row["required_markings"],
                    "submissionCriteria": row["submission_criteria"]}
        if snapshot != _ACTION:
            raise ModelEvalActionBlocked("MODEL_EVAL_ACTION_TYPE_DRIFTED")
        return {**snapshot, "revisionHash": canonical_hash(snapshot)}

    @staticmethod
    def _role(conn: Any, scope: TenantScope, actor: str) -> str:
        rows = conn.execute("""SELECT role FROM meta_membership
            WHERE org_id=%s AND project_id=%s AND subject=%s FOR SHARE""",
            (*scope.key, actor)).fetchall()
        if len(rows) != 1 or rows[0]["role"].lower() not in {"owner", "admin"}:
            raise ModelEvalActionBlocked("MODEL_EVAL_CURRENT_OWNER_REQUIRED")
        return rows[0]["role"]

    @staticmethod
    def _request(conn: Any, scope: TenantScope, request_id: str,
                 request_hash: str) -> tuple[ModelEvalRequestCreate, str]:
        row = conn.execute("""SELECT request_hash,request_json,created_by,expires_at
            FROM aip_model_eval_request WHERE org_id=%s AND project_id=%s AND request_id=%s""",
            (*scope.key, request_id)).fetchone()
        if (row is None or row["request_hash"] != request_hash
            or canonical_hash(row["request_json"]) != request_hash
            or row["expires_at"] <= datetime.now(UTC)):
            raise ModelEvalActionBlocked("MODEL_EVAL_APPLICATION_NOT_CURRENT")
        try:
            request = ModelEvalRequestCreate.model_validate(row["request_json"])
        except (TypeError, ValueError) as exc:
            raise ModelEvalActionBlocked("MODEL_EVAL_APPLICATION_INVALID") from exc
        try:
            AipModelEvalRequestStore().require_current(conn, scope, request)
        except ModelEvalRequestBlocked as exc:
            raise ModelEvalActionBlocked("MODEL_EVAL_APPLICATION_DEPENDENCY_DRIFTED") from exc
        return request, row["created_by"]

    def check_request(self, conn: Any, scope: TenantScope, actor: str,
                      body: CreateActionProposalRequest, action_snapshot: dict[str, Any],
                      risk: RiskDecision) -> str:
        if (body.action_type_id != ACTION_ID or action_snapshot != self.read_metadata(conn)
            or body.purpose != "quality-eval" or body.task_id is not None
            or body.run_id is not None or body.object_ref is not None
            or body.impact_preview_ref is not None or body.diff or body.evidence_refs
            or body.risk_hint is not None or openfga_api_url()
            or set(body.payload) != {"requestId", "requestHash"}
            or not isinstance(body.payload["requestId"], str)
            or not isinstance(body.payload["requestHash"], str)):
            raise ModelEvalActionBlocked("MODEL_EVAL_PROPOSAL_SHAPE_REQUIRED")
        current_risk = classify_action_risk(ACTION_ID, action_snapshot, body.payload, None)
        if (risk != current_risk or risk.level is not ActionRiskLevel.R2
            or risk.approval_policy.get("makerChecker") is not True
            or risk.approval_policy.get("executionAllowed") is not False
            or risk.approval_policy.get("draftOnly") is not False):
            raise ModelEvalActionBlocked("MODEL_EVAL_APPROVAL_POLICY_REQUIRED")
        identity = conn.execute("SELECT current_user AS role,current_setting('aos.org_id',true) AS org_id,"
                                "current_setting('aos.project_id',true) AS project_id").fetchone()
        if (identity["role"], identity["org_id"], identity["project_id"]) != (
            "aos_runtime", *scope.key,
        ):
            raise ModelEvalActionBlocked("MODEL_EVAL_TENANT_ROLE_REQUIRED")
        request, maker = self._request(conn, scope, body.payload["requestId"],
                                       body.payload["requestHash"])
        if actor != maker or body.effective_expiry() > request.expires_at:
            raise ModelEvalActionBlocked("MODEL_EVAL_MAKER_OR_EXPIRY_DRIFTED")
        self._role(conn, scope, actor)
        return canonical_hash({"requestId": body.payload["requestId"],
                               "requestHash": body.payload["requestHash"],
                               "actionTypeRevisionHash": action_snapshot["revisionHash"]})

    def check_proposal(self, conn: Any, scope: TenantScope, actor: str,
                       row: dict[str, Any], *, checker: bool) -> tuple[str, ...] | None:
        if (row["action_type_id"] != ACTION_ID
            or row["action_type_snapshot"].get("id") != ACTION_ID
            or row["task_id"] is not None or row["run_id"] is not None
            or row["object_ref"] is not None or row["impact_preview_id"] is not None
            or row["diff"] != {} or row["evidence_refs"] != []
            or row["client_risk_hint"] is not None):
            raise ModelEvalActionBlocked("MODEL_EVAL_PROPOSAL_DRIFTED")
        body = CreateActionProposalRequest(
            actionTypeId=ACTION_ID, purpose=row["purpose"], payload=row["payload"],
            expiresAt=row["expires_at"],
        )
        risk = classify_action_risk(ACTION_ID, row["action_type_snapshot"], row["payload"], None)
        policy = {"floor": risk.floor.value, "reasons": list(risk.reasons),
                  **risk.approval_policy}
        binding = self.check_request(conn, scope, row["created_by"], body,
                                     row["action_type_snapshot"], risk)
        if (row["risk_level"] != risk.level.value or row["policy_snapshot"] != policy
            or row["approval_policy_hash"] != canonical_hash(policy)
            or row["action_binding_hash"] != binding):
            raise ModelEvalActionBlocked("MODEL_EVAL_BINDING_DRIFTED")
        draft = conn.execute("""SELECT snapshot FROM aip_action_draft
            WHERE org_id=%s AND project_id=%s AND proposal_id=%s""",
            (*scope.key, row["proposal_id"])).fetchone()
        stable = draft["snapshot"] if draft else None
        if (not isinstance(stable, dict) or canonical_hash(stable) != row["proposal_hash"]
            or stable.get("actionBindingHash") != binding
            or stable.get("actionType") != row["action_type_snapshot"]
            or stable.get("payload") != row["payload"]
            or stable.get("policy") != row["policy_snapshot"]):
            raise ModelEvalActionBlocked("MODEL_EVAL_DRAFT_DRIFTED")
        if not checker:
            if actor != row["created_by"]:
                raise ModelEvalActionBlocked("MODEL_EVAL_REPLAY_MAKER_REQUIRED")
            return None
        if actor == row["created_by"]:
            raise ModelEvalActionBlocked("MODEL_EVAL_INDEPENDENT_CHECKER_REQUIRED")
        return (self._role(conn, scope, actor),)


def propose_model_eval_request(principal: Principal, request_id: str,
                               idempotency_key: str, expires_at: datetime,
                               *, connect_factory=None):
    if (type(principal) is not Principal or principal.token_kind != "oidc"
        or type(request_id) is not str or not request_id or request_id.strip() != request_id
        or type(idempotency_key) is not str or not idempotency_key
        or idempotency_key.strip() != idempotency_key
        or type(expires_at) is not datetime or expires_at.tzinfo is None
        or expires_at <= datetime.now(UTC)):
        raise ModelEvalActionBlocked("MODEL_EVAL_OIDC_MAKER_INPUT_REQUIRED")
    scope = TenantScope(principal.org_id, principal.project_id)
    factory = connect_factory or db_connect
    guard = ModelEvalActionGuard()
    with factory(scope) as conn:
        snapshot = guard.read_metadata(conn)
        row = conn.execute("""SELECT request_hash FROM aip_model_eval_request
            WHERE org_id=%s AND project_id=%s AND request_id=%s""",
            (*scope.key, request_id)).fetchone()
        if row is None:
            raise ModelEvalActionBlocked("MODEL_EVAL_APPLICATION_NOT_CURRENT")
        payload = {"requestId": request_id, "requestHash": row["request_hash"]}
    body = CreateActionProposalRequest(
        actionTypeId=ACTION_ID, purpose="quality-eval", payload=payload,
        expiresAt=expires_at,
    )
    risk = classify_action_risk(ACTION_ID, snapshot, payload, None)
    return AipActionStore(factory, model_eval_guard=guard).create_proposal(
        scope, principal.subject, idempotency_key, body, snapshot, risk,
    )


def decide_model_eval_request(principal: Principal, proposal_id: str,
                              idempotency_key: str, body: DecideActionProposalRequest,
                              *, connect_factory=None):
    if (type(principal) is not Principal or principal.token_kind != "oidc"
        or type(proposal_id) is not str or not proposal_id or proposal_id.strip() != proposal_id
        or type(idempotency_key) is not str or not idempotency_key
        or idempotency_key.strip() != idempotency_key
        or type(body) is not DecideActionProposalRequest):
        raise ModelEvalActionBlocked("MODEL_EVAL_OIDC_CHECKER_INPUT_REQUIRED")
    if body.approval_expires_at is not None and body.approval_expires_at.utcoffset() is None:
        raise ModelEvalActionBlocked("MODEL_EVAL_CHECKER_EXPIRY_INVALID")
    scope = TenantScope(principal.org_id, principal.project_id)
    return AipActionStore(connect_factory or db_connect,
                          model_eval_guard=ModelEvalActionGuard()).decide(
        scope, principal.subject, proposal_id, idempotency_key, body,
    )


__all__ = ["ACTION_ID", "ModelEvalActionGuard", "ModelEvalActionBlocked",
           "propose_model_eval_request", "decide_model_eval_request"]

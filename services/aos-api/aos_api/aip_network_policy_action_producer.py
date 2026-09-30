"""Dedicated, fail-closed producer for a network activation Action Proposal.

The proposal remains drafted. This module neither approves nor activates a policy.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from aos_api.aip_action_models import ActionDraftBundle, CreateActionProposalRequest, DecideActionProposalRequest
from aos_api.aip_action_policy import classify_action_risk
from aos_api.aip_action_store import AipActionStore, AipActionTransitionBlocked, canonical_hash
from aos_api.aip_contracts import ActionRiskLevel, AipContractModel, ApprovalDecision
from aos_api.aip_network_policy_activation_target import (
    NetworkPolicyActivationTargetBlocked,
    build_network_policy_activation_target,
)
from aos_api.aip_network_policy_contracts import NetworkPolicyRevisionCreate
from aos_api.aip_network_policy_store import AipNetworkPolicyStore, NetworkPolicyDependencyBlocked
from aos_api.auth import Principal
from aos_api.db import connect as db_connect
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.openfga import openfga_api_url
from aos_api.tenant_scope import TenantScope


ACTION_ID = "aip_activate_network_policy"
OBJECT_ID = "NetworkPolicyRevision"
_ACTION = {"id": ACTION_ID, "name": "激活网络策略", "objectType": OBJECT_ID,
           "parameters": [], "requiredMarkings": [], "submissionCriteria": []}
_OBJECT = {"id": OBJECT_ID, "name": "网络策略修订", "description": "受控网络策略激活目标",
           "published": True, "properties": [], "requiredMarkings": []}


class NetworkPolicyProducerBlocked(ValueError):
    pass


class NetworkActivationProposalRequest(AipContractModel):
    candidate: NetworkPolicyRevisionCreate
    expires_at: datetime


class NetworkPolicyActivationGuard:
    """Recheck exact metadata, actor and target inside the Action write transaction."""

    def __init__(self, *, scope: TenantScope, actor: str,
                 candidate: NetworkPolicyRevisionCreate, expected_version: int,
                 expires_at: datetime) -> None:
        self.scope = scope
        self.actor = actor
        self.candidate = candidate
        self.expected_version = expected_version
        self.expires_at = expires_at

    def read_metadata(self, conn: Any) -> dict[str, Any]:
        object_row = conn.execute(
            "SELECT id,name,description,published,properties,required_markings "
            "FROM meta_object_type WHERE id=%s FOR SHARE", (OBJECT_ID,),
        ).fetchone()
        if object_row is None or dict(object_row) != {
            "id": _OBJECT["id"], "name": _OBJECT["name"],
            "description": _OBJECT["description"], "published": _OBJECT["published"],
            "properties": _OBJECT["properties"], "required_markings": _OBJECT["requiredMarkings"],
        }:
            raise NetworkPolicyProducerBlocked("FORMAL_NETWORK_OBJECT_TYPE_UNAVAILABLE")
        row = conn.execute(
            "SELECT id,name,object_type,parameters,required_markings,submission_criteria "
            "FROM meta_action_type WHERE id=%s FOR SHARE", (ACTION_ID,),
        ).fetchone()
        if row is None:
            raise NetworkPolicyProducerBlocked("FORMAL_NETWORK_ACTION_TYPE_UNAVAILABLE")
        snapshot = {
            "id": row["id"], "name": row["name"], "objectType": row["object_type"],
            "parameters": row["parameters"], "requiredMarkings": row["required_markings"],
            "submissionCriteria": row["submission_criteria"],
        }
        if snapshot != _ACTION:
            raise NetworkPolicyProducerBlocked("FORMAL_NETWORK_ACTION_TYPE_DRIFTED")
        return {**snapshot, "revisionHash": canonical_hash(snapshot)}

    def check_request(self, conn: Any, scope: TenantScope, actor: str,
                      body: CreateActionProposalRequest, action_snapshot: dict[str, Any], risk) -> str:
        if (scope != self.scope or actor != self.actor or body.action_type_id != ACTION_ID
                or action_snapshot != self.read_metadata(conn)):
            raise NetworkPolicyProducerBlocked("NETWORK_PRODUCER_IDENTITY_OR_METADATA_DRIFTED")
        if openfga_api_url():
            raise NetworkPolicyProducerBlocked("REMOTE_POLICY_MEMBERSHIP_ADAPTER_REQUIRED")
        db_identity = conn.execute(
            "SELECT current_user AS role,current_setting('aos.org_id',true) AS org_id,"
            "current_setting('aos.project_id',true) AS project_id",
        ).fetchone()
        if db_identity is None or (db_identity["role"], db_identity["org_id"], db_identity["project_id"]) != (
            "aos_runtime", *scope.key,
        ):
            raise NetworkPolicyProducerBlocked("NETWORK_PRODUCER_TENANT_ROLE_REQUIRED")
        members = conn.execute(
            "SELECT role FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s FOR SHARE",
            (*scope.key, actor),
        ).fetchall()
        if len(members) != 1 or members[0]["role"].lower() not in {"owner", "admin"}:
            raise NetworkPolicyProducerBlocked("NETWORK_PRODUCER_CURRENT_OWNER_REQUIRED")
        head = conn.execute(
            "SELECT current_revision,version FROM aip_network_policy_head "
            "WHERE org_id=%s AND project_id=%s AND policy_id=%s FOR UPDATE",
            (*scope.key, self.candidate.policy_id),
        ).fetchone()
        head_revision = int(head["current_revision"]) if head else 0
        head_version = int(head["version"]) if head else 0
        if head_version != self.expected_version:
            raise NetworkPolicyProducerBlocked("NETWORK_PRODUCER_HEAD_VERSION_DRIFTED")
        try:
            target = build_network_policy_activation_target(
                scope=scope, candidate=self.candidate,
                expected_head_revision=head_revision, expected_head_version=head_version,
            )
            factory = TransactionBoundConnectFactory(HostTransaction(conn), scope)
            AipNetworkPolicyStore(factory)._require_egress(scope, self.candidate)
        except (NetworkPolicyActivationTargetBlocked, NetworkPolicyDependencyBlocked) as exc:
            raise NetworkPolicyProducerBlocked("NETWORK_PRODUCER_TARGET_OR_EGRESS_INVALID") from exc
        expected_payload = {
            "candidate": self.candidate.model_dump(mode="json", by_alias=True),
            "expectedHeadRevision": head_revision,
            "expectedHeadVersion": head_version,
            "targetContentHash": target.target_content_hash,
            "bindingHash": target.binding_hash,
        }
        expected_risk = classify_action_risk(ACTION_ID, action_snapshot, expected_payload, None)
        if (body.payload != expected_payload or body.task_id is not None or body.run_id is not None
                or body.impact_preview_ref is not None or body.risk_hint is not None
                or body.expires_at != self.expires_at or risk != expected_risk
                or risk.level is not ActionRiskLevel.R2
                or risk.approval_policy.get("makerChecker") is not True
                or risk.approval_policy.get("draftOnly") is not False):
            raise NetworkPolicyProducerBlocked("NETWORK_PRODUCER_PROPOSAL_DRIFTED")
        return target.binding_hash

    def check_replay(self, conn: Any, scope: TenantScope, actor: str, row: Any,
                     *, allowed_statuses: tuple[str, ...] = ('drafted',)) -> None:
        if (row['created_by'] != actor or row['status'] not in allowed_statuses
                or row['task_id'] is not None or row['run_id'] is not None
                or row['impact_preview_id'] is not None or row['object_ref'] is not None
                or row['diff'] != {} or row['evidence_refs'] != []):
            raise NetworkPolicyProducerBlocked('NETWORK_PRODUCER_REPLAY_DRIFTED')
        body = CreateActionProposalRequest(
            actionTypeId=ACTION_ID, purpose=row['purpose'], payload=row['payload'],
            expiresAt=row['expires_at'],
        )
        risk = classify_action_risk(ACTION_ID, row['action_type_snapshot'], row['payload'], None)
        policy = {"floor": risk.floor.value, "reasons": list(risk.reasons), **risk.approval_policy}
        if (row['risk_level'] != risk.level.value or row['policy_snapshot'] != policy
                or row['approval_policy_hash'] != canonical_hash(policy)
                or row['action_binding_hash'] != self.check_request(
                    conn, scope, actor, body, row['action_type_snapshot'], risk,
                )):
            raise NetworkPolicyProducerBlocked('NETWORK_PRODUCER_REPLAY_DRIFTED')


class NetworkPolicyApprovalGuard:
    """Validate a distinct current checker and the immutable proposal in the decide transaction."""

    def __init__(self, *, scope: TenantScope, checker: str, decision: ApprovalDecision) -> None:
        self.scope = scope
        self.checker = checker
        self.decision = decision

    def check(self, conn: Any, scope: TenantScope, actor: str, row: Any) -> tuple[str, ...]:
        if (scope != self.scope or actor != self.checker or row['action_type_id'] != ACTION_ID
                or row['action_type_snapshot'].get('id') != ACTION_ID):
            raise NetworkPolicyProducerBlocked('NETWORK_CHECKER_PROPOSAL_IDENTITY_DRIFTED')
        if actor == row['created_by']:
            raise NetworkPolicyProducerBlocked('NETWORK_MAKER_CHECKER_SEPARATION_REQUIRED')
        members = conn.execute(
            "SELECT role FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s FOR SHARE",
            (*scope.key, actor),
        ).fetchall()
        if len(members) != 1 or members[0]['role'].lower() not in {'owner', 'admin'}:
            raise NetworkPolicyProducerBlocked('NETWORK_CURRENT_CHECKER_REQUIRED')
        if row['status'] == 'approved' and self.decision is ApprovalDecision.APPROVED:
            prior = conn.execute(
                "SELECT 1 FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s "
                "AND proposal_id=%s AND actor_id=%s AND decision='approved'",
                (*scope.key, row['proposal_id'], actor),
            ).fetchone()
            if prior is None:
                raise NetworkPolicyProducerBlocked('NETWORK_ALREADY_APPROVED')
        try:
            candidate = NetworkPolicyRevisionCreate.model_validate(row['payload']['candidate'])
            expected_version = row['payload']['expectedHeadVersion']
            if type(expected_version) is not int or expected_version < 0:
                raise ValueError('invalid head version')
            guard = NetworkPolicyActivationGuard(
                scope=scope, actor=row['created_by'], candidate=candidate,
                expected_version=expected_version, expires_at=row['expires_at'],
            )
            guard.check_replay(conn, scope, row['created_by'], row,
                               allowed_statuses=('drafted', 'approved', 'rejected'))
        except (KeyError, TypeError, ValueError) as exc:
            raise NetworkPolicyProducerBlocked('NETWORK_CHECKER_BINDING_DRIFTED') from exc
        draft = conn.execute(
            "SELECT snapshot FROM aip_action_draft WHERE org_id=%s AND project_id=%s AND proposal_id=%s",
            (*scope.key, row['proposal_id']),
        ).fetchone()
        stable = draft['snapshot'] if draft else None
        if (not isinstance(stable, dict) or canonical_hash(stable) != row['proposal_hash']
                or stable.get('actionBindingHash') != row['action_binding_hash']
                or stable.get('actionType') != row['action_type_snapshot']
                or stable.get('payload') != row['payload']
                or stable.get('policy') != row['policy_snapshot']):
            raise NetworkPolicyProducerBlocked('NETWORK_CHECKER_DRAFT_DRIFTED')
        return (members[0]['role'],)


def propose_network_activation(
    principal: Principal, candidate: NetworkPolicyRevisionCreate, *, expected_version: int,
    idempotency_key: str, expires_at: datetime, connect_factory=None,
) -> ActionDraftBundle:
    if type(principal) is not Principal or principal.token_kind != "oidc":
        raise NetworkPolicyProducerBlocked("OIDC_POLICY_MAKER_REQUIRED")
    if (type(candidate) is not NetworkPolicyRevisionCreate or type(expected_version) is not int
            or expected_version < 0 or type(idempotency_key) is not str
            or not 1 <= len(idempotency_key.strip()) <= 120 or idempotency_key != idempotency_key.strip()):
        raise NetworkPolicyProducerBlocked("NETWORK_PRODUCER_INPUT_INVALID")
    now = datetime.now(UTC)
    if (type(expires_at) is not datetime or expires_at.tzinfo is None
            or not now < expires_at <= now + timedelta(minutes=15)):
        raise NetworkPolicyProducerBlocked("NETWORK_PRODUCER_EXPIRY_INVALID")
    if (type(principal.subject) is not str or not principal.subject
            or principal.subject != principal.subject.strip() or not principal.subject.isprintable()):
        raise NetworkPolicyProducerBlocked("NETWORK_PRODUCER_ACTOR_INVALID")
    scope = TenantScope(principal.org_id, principal.project_id)
    guard = NetworkPolicyActivationGuard(
        scope=scope, actor=principal.subject, candidate=candidate,
        expected_version=expected_version, expires_at=expires_at,
    )
    with (connect_factory or db_connect)(scope) as conn:
        snapshot = guard.read_metadata(conn)
        target = build_network_policy_activation_target(
            scope=scope, candidate=candidate,
            expected_head_revision=candidate.revision - 1,
            expected_head_version=expected_version,
        )
        payload = {
            "candidate": candidate.model_dump(mode="json", by_alias=True),
            "expectedHeadRevision": target.expected_head_revision,
            "expectedHeadVersion": target.expected_head_version,
            "targetContentHash": target.target_content_hash,
            "bindingHash": target.binding_hash,
        }
        body = CreateActionProposalRequest(
            actionTypeId=ACTION_ID, purpose="申请激活精确网络策略修订，等待独立审批",
            payload=payload, expiresAt=expires_at,
        )
        risk = classify_action_risk(ACTION_ID, snapshot, payload, None)
        factory = TransactionBoundConnectFactory(HostTransaction(conn), scope)
        return AipActionStore(factory, network_activation_guard=guard).create_proposal(
            scope, principal.subject, idempotency_key, body, snapshot, risk,
        )


def decide_network_activation(
    principal: Principal, proposal_id: str, idempotency_key: str,
    body: DecideActionProposalRequest, *, connect_factory=None,
) -> ActionDraftBundle:
    if type(principal) is not Principal or principal.token_kind != 'oidc':
        raise NetworkPolicyProducerBlocked('OIDC_POLICY_CHECKER_REQUIRED')
    if (type(proposal_id) is not str or not proposal_id or proposal_id != proposal_id.strip()
            or type(idempotency_key) is not str or not 1 <= len(idempotency_key.strip()) <= 120
            or idempotency_key != idempotency_key.strip()
            or type(body) is not DecideActionProposalRequest):
        raise NetworkPolicyProducerBlocked('NETWORK_CHECKER_INPUT_INVALID')
    if body.approval_expires_at is not None and body.approval_expires_at.tzinfo is None:
        raise NetworkPolicyProducerBlocked('NETWORK_CHECKER_EXPIRY_INVALID')
    if connect_factory is None:
        raise NetworkPolicyProducerBlocked('NETWORK_ISSUER_SERVICE_REQUIRED')
    scope = TenantScope(principal.org_id, principal.project_id)
    guard = NetworkPolicyApprovalGuard(scope=scope, checker=principal.subject, decision=body.decision)
    return AipActionStore(connect_factory, network_approval_guard=guard).decide(
        scope, principal.subject, proposal_id, idempotency_key, body)

"""Exact draft sources for formal Egress/Data/Quota activation.

Source validation alone grants no approval and performs no activation or commit.
"""
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from psycopg.types.json import Jsonb
from pydantic import ValidationError

from aos_api.aip_runtime_guard_policy_contracts import (
    DataClassificationPolicyRevision, DataClassificationPolicyRevisionCreate,
    EgressPolicyRevision, EgressPolicyRevisionCreate, GuardPolicyLifecycle,
)
from aos_api.aip_model_governance_policy_contracts import QuotaPolicyRevision, QuotaPolicyRevisionCreate
from aos_api.aip_runtime_guard_policy_store import canonical_hash
from aos_api.tenant_scope import TenantScope


class GuardActivationBlocked(ValueError):
    pass


_SPECS = {
    QuotaPolicyRevisionCreate: ("quota", QuotaPolicyRevision, "QuotaPolicyRevision", "aip_activate_quota_policy"),
    EgressPolicyRevisionCreate: ("egress", EgressPolicyRevision, "EgressPolicyRevision", "aip_activate_egress_policy"),
    DataClassificationPolicyRevisionCreate: (
        "data_classification", DataClassificationPolicyRevision,
        "DataClassificationPolicyRevision", "aip_activate_data_policy"),
}
_REVISION_FIELDS = {"tenant", "contentHash", "createdBy", "createdAt"}


@dataclass(frozen=True, slots=True)
class GuardActivationTarget:
    scope: TenantScope
    kind: str
    action_type_id: str
    policy_id: str
    revision: int
    expected_head_revision: int
    expected_head_version: int
    source_content_hash: str
    target_content_hash: str
    binding_hash: str


def build_guard_activation_target(*, scope, draft, candidate, expected_version):
    spec = _SPECS.get(type(candidate))
    if (type(scope) is not TenantScope or spec is None or type(draft) is not spec[1]
            or type(expected_version) is not int or expected_version < 1):
        raise GuardActivationBlocked("GUARD_TARGET_INVALID")
    try:
        # Reparse serialized values: model_copy/model_construct skip validation.
        source = type(draft).model_validate(draft.model_dump(mode="json", by_alias=True))
        active = type(candidate).model_validate(candidate.model_dump(mode="json", by_alias=True))
    except (ValidationError, TypeError, ValueError) as exc:
        raise GuardActivationBlocked("GUARD_TARGET_INVALID") from exc
    source_content = {k: v for k, v in source.model_dump(mode="json", by_alias=True).items()
                      if k not in _REVISION_FIELDS}
    active_content = active.model_dump(mode="json", by_alias=True)
    if (source.tenant.org_id, source.tenant.project_id) != scope.key:
        raise GuardActivationBlocked("GUARD_SOURCE_TENANT_DRIFTED")
    if (source.lifecycle.value != "draft"
            or active.lifecycle.value != "active"
            or active.revision != source.revision + 1
            or source.content_hash != canonical_hash(source_content)
            or active_content != {**source_content, "revision": source.revision + 1, "lifecycle": "active"}):
        raise GuardActivationBlocked("GUARD_SOURCE_CONTENT_DRIFTED")
    target_hash = canonical_hash(active_content)
    binding = canonical_hash({
        "schema": "aos-guard-policy-activation/v1",
        "tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
        "actionTypeId": spec[3], "policyKind": spec[0], "policyId": active.policy_id,
        "revision": active.revision, "expectedHeadRevision": source.revision,
        "expectedHeadVersion": expected_version, "sourceContentHash": source.content_hash,
        "targetContentHash": target_hash,
    })
    return GuardActivationTarget(scope, spec[0], spec[3], active.policy_id, active.revision,
                                 source.revision, expected_version, source.content_hash, target_hash, binding)


def read_guard_activation_source(conn, scope, candidate, *, expected_version):
    """Lock and validate the current Store draft in the caller's transaction."""
    spec = _SPECS.get(type(candidate))
    if (type(scope) is not TenantScope or spec is None
            or type(expected_version) is not int or expected_version < 1):
        raise GuardActivationBlocked("GUARD_SOURCE_INPUT_INVALID")
    identity = conn.execute(
        "SELECT current_user AS role,current_setting('aos.org_id',true) AS org_id,"
        "current_setting('aos.project_id',true) AS project_id").fetchone()
    if not identity or (identity["role"], identity["org_id"], identity["project_id"]) != ("aos_runtime", *scope.key):
        raise GuardActivationBlocked("GUARD_SOURCE_TENANT_ROLE_REQUIRED")
    # Closed code-owned table selection; no request-controlled SQL identifier.
    prefix = "aip_model_governance_policy" if spec[0] == "quota" else "aip_runtime_guard_policy"
    operation_prefix = "model_governance_policy" if spec[0] == "quota" else "runtime_guard_policy"
    head = conn.execute(
        f"SELECT current_revision,version FROM {prefix}_head "
        "WHERE org_id=%s AND project_id=%s AND policy_kind=%s AND policy_id=%s FOR UPDATE",
        (*scope.key, spec[0], candidate.policy_id)).fetchone()
    if (not head or head["version"] != expected_version or head["current_revision"] != candidate.revision - 1):
        raise GuardActivationBlocked("GUARD_SOURCE_HEAD_DRIFTED")
    row = conn.execute(
        "SELECT content_hash,lifecycle,effective_from,effective_until,payload,created_by,created_at "
        f"FROM {prefix}_revision WHERE org_id=%s AND project_id=%s "
        "AND policy_kind=%s AND policy_id=%s AND revision=%s",
        (*scope.key, spec[0], candidate.policy_id, head["current_revision"])).fetchone()
    if row is None:
        raise GuardActivationBlocked("GUARD_SOURCE_REVISION_MISSING")
    try:
        draft = spec[1].model_validate(row["payload"])
    except (ValidationError, TypeError, ValueError) as exc:
        raise GuardActivationBlocked("GUARD_SOURCE_PAYLOAD_INVALID") from exc
    if (draft.policy_id != candidate.policy_id or draft.revision != head["current_revision"]
            or (row["content_hash"], row["lifecycle"], row["effective_from"], row["effective_until"],
                row["created_by"], row["created_at"]) !=
               (draft.content_hash, draft.lifecycle.value, draft.effective_from, draft.effective_until,
                draft.created_by, draft.created_at)):
        raise GuardActivationBlocked("GUARD_SOURCE_COLUMN_DRIFTED")
    target = build_guard_activation_target(scope=scope, draft=draft, candidate=candidate,
                                           expected_version=expected_version)
    source_ref = {"resourceType": spec[2], "resourceId": draft.policy_id,
                  "revision": draft.revision, "contentHash": draft.content_hash}
    receipts = conn.execute(
        f"SELECT request_hash,created_by FROM {prefix}_receipt "
        "WHERE org_id=%s AND project_id=%s AND operation=%s AND result_ref=%s",
        (*scope.key, f"{operation_prefix}.{spec[0]}.publish", Jsonb(source_ref))).fetchall()
    content = {k: v for k, v in draft.model_dump(mode="json", by_alias=True).items()
               if k not in _REVISION_FIELDS}
    if (len(receipts) != 1 or receipts[0]["created_by"] != draft.created_by
            or receipts[0]["request_hash"] != canonical_hash({"expectedVersion": expected_version - 1,
                                                           "revision": content})):
        raise GuardActivationBlocked("GUARD_SOURCE_RECEIPT_REQUIRED")
    return target


class GuardPolicyActivationGuard:
    """Revalidate exact maker, metadata and source in the Action write transaction."""

    def __init__(self, *, scope, actor, candidate, expected_version, expires_at):
        self.scope, self.actor, self.candidate = scope, actor, candidate
        self.expected_version, self.expires_at = expected_version, expires_at

    def read_metadata(self, conn):
        spec = _SPECS[type(self.candidate)]
        name = {"egress": "出口策略", "data_classification": "数据分类策略", "quota": "配额策略"}[spec[0]]
        obj = conn.execute(
            "SELECT id,name,description,published,properties,required_markings FROM meta_object_type "
            "WHERE id=%s FOR SHARE", (spec[2],)).fetchone()
        if obj is None or dict(obj) != {
            "id": spec[2], "name": name+"修订", "description": "受控"+name+"激活目标",
            "published": True, "properties": [], "required_markings": [],
        }:
            raise GuardActivationBlocked("GUARD_OBJECT_METADATA_DRIFTED")
        row = conn.execute(
            "SELECT id,name,object_type,parameters,required_markings,submission_criteria "
            "FROM meta_action_type WHERE id=%s FOR SHARE", (spec[3],)).fetchone()
        if row is None or dict(row) != {
            "id": spec[3], "name": "激活"+name, "object_type": spec[2], "parameters": [],
            "required_markings": [], "submission_criteria": [],
        }:
            raise GuardActivationBlocked("GUARD_ACTION_METADATA_DRIFTED")
        snapshot = {"id": spec[3], "name": "激活"+name, "objectType": spec[2], "parameters": [],
                    "requiredMarkings": [], "submissionCriteria": []}
        return {**snapshot, "revisionHash": canonical_hash(snapshot)}

    def request(self, conn):
        from aos_api.aip_action_models import CreateActionProposalRequest
        target = read_guard_activation_source(conn, self.scope, self.candidate,
                                               expected_version=self.expected_version)
        return CreateActionProposalRequest(
            actionTypeId=target.action_type_id, purpose="申请激活精确运行守护策略修订，等待独立审批",
            payload={"candidate": self.candidate.model_dump(mode="json", by_alias=True),
                     "expectedHeadRevision": target.expected_head_revision,
                     "expectedHeadVersion": target.expected_head_version,
                     "sourceContentHash": target.source_content_hash,
                     "targetContentHash": target.target_content_hash, "bindingHash": target.binding_hash},
            expiresAt=self.expires_at)

    def check_request(self, conn, scope, actor, body, action_snapshot, risk):
        from aos_api.aip_action_policy import classify_action_risk
        from aos_api.aip_contracts import ActionRiskLevel
        from aos_api.openfga import openfga_api_url
        if scope != self.scope or actor != self.actor or action_snapshot != self.read_metadata(conn):
            raise GuardActivationBlocked("GUARD_MAKER_OR_METADATA_DRIFTED")
        if openfga_api_url():
            raise GuardActivationBlocked("REMOTE_POLICY_MEMBERSHIP_ADAPTER_REQUIRED")
        members = conn.execute(
            "SELECT role FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s FOR SHARE",
            (*scope.key, actor)).fetchall()
        if len(members) != 1 or members[0]["role"].lower() not in {"owner", "admin"}:
            raise GuardActivationBlocked("GUARD_CURRENT_OWNER_REQUIRED")
        expected = self.request(conn)
        expected_risk = classify_action_risk(expected.action_type_id, action_snapshot, expected.payload, None)
        now = datetime.now(UTC)
        if (body != expected or risk != expected_risk or risk.level is not ActionRiskLevel.R2
                or risk.approval_policy.get("makerChecker") is not True
                or risk.approval_policy.get("draftOnly") is not False
                or not now < self.expires_at <= min(now+timedelta(minutes=15), self.candidate.effective_until)
                or self.candidate.effective_from > now):
            raise GuardActivationBlocked("GUARD_PROPOSAL_OR_EXPIRY_DRIFTED")
        return expected.payload["bindingHash"]

    def check_replay(self, conn, scope, actor, row):
        from aos_api.aip_action_policy import classify_action_risk
        if (row["created_by"] != actor or row["status"] != "drafted"
                or row["task_id"] is not None or row["run_id"] is not None
                or row["impact_preview_id"] is not None or row["object_ref"] is not None
                or row["diff"] != {} or row["evidence_refs"] != []):
            raise GuardActivationBlocked("GUARD_REPLAY_DRIFTED")
        expected = self.request(conn)
        risk = classify_action_risk(expected.action_type_id, row["action_type_snapshot"], row["payload"], None)
        binding = self.check_request(conn, scope, actor, expected, row["action_type_snapshot"], risk)
        policy = {"floor": risk.floor.value, "reasons": list(risk.reasons), **risk.approval_policy}
        if (row["payload"] != expected.payload or row["purpose"] != expected.purpose
                or row["expires_at"] != self.expires_at or row["action_type_id"] != expected.action_type_id
                or row["risk_level"] != risk.level.value or row["policy_snapshot"] != policy
                or row["approval_policy_hash"] != canonical_hash(policy) or row["action_binding_hash"] != binding):
            raise GuardActivationBlocked("GUARD_REPLAY_DRIFTED")


class GuardPolicyApprovalGuard:
    """Independent checker for one undecided immutable Proposal."""

    def __init__(self, *, scope, checker):
        self.scope, self.checker = scope, checker

    def check(self, conn, scope, actor, row):
        identity = conn.execute("SELECT session_user AS login,current_user AS role").fetchone()
        if identity != {"login": "aos_guard_approval_issuer", "role": "aos_runtime"}:
            raise GuardActivationBlocked("GUARD_ISSUER_IDENTITY_REQUIRED")
        if scope != self.scope or actor != self.checker or actor == row["created_by"]:
            raise GuardActivationBlocked("GUARD_INDEPENDENT_CHECKER_REQUIRED")
        members = conn.execute(
            "SELECT role FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s FOR SHARE",
            (*scope.key, actor)).fetchall()
        if len(members) != 1 or members[0]["role"].lower() not in {"owner", "admin"}:
            raise GuardActivationBlocked("GUARD_CURRENT_CHECKER_REQUIRED")
        creates = {spec[3]: model for model, spec in _SPECS.items()}
        try:
            create_type = creates[row["action_type_id"]]
            candidate = create_type.model_validate(row["payload"]["candidate"])
            guard = GuardPolicyActivationGuard(scope=scope, actor=row["created_by"], candidate=candidate,
                expected_version=row["payload"]["expectedHeadVersion"], expires_at=row["expires_at"])
            guard.check_replay(conn, scope, row["created_by"], row)
        except (KeyError, ValueError, TypeError) as exc:
            raise GuardActivationBlocked("GUARD_CHECKER_SOURCE_DRIFTED") from exc
        draft = conn.execute("SELECT * FROM aip_action_draft WHERE org_id=%s AND project_id=%s AND proposal_id=%s",
                             (*scope.key, row["proposal_id"])).fetchone()
        stable = draft["snapshot"] if draft else None
        if (not isinstance(stable, dict) or canonical_hash(stable) != row["proposal_hash"]
                or stable.get("tenantScope") != {"orgId": scope.org_id, "projectId": scope.project_id}
                or stable.get("createdBy") != row["created_by"]
                or stable.get("actionBindingHash") != row["action_binding_hash"]
                or stable.get("approvalPolicyHash") != row["approval_policy_hash"]
                or stable.get("actionType") != row["action_type_snapshot"]
                or stable.get("payload") != row["payload"] or stable.get("policy") != row["policy_snapshot"]
                or draft["proposal_hash"] != row["proposal_hash"] or draft["proposal_version"] != 1
                or draft["status"] != "awaiting_approval" or row["version"] != 1
                or row["source_draft_id"] is not None or row["client_risk_hint"] is not None):
            raise GuardActivationBlocked("GUARD_CHECKER_DRAFT_DRIFTED")
        if conn.execute("SELECT 1 FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND proposal_id=%s",
                        (*scope.key, row["proposal_id"])).fetchone():
            raise GuardActivationBlocked("GUARD_ALREADY_DECIDED")
        if conn.execute("SELECT 1 FROM aip_action_withdrawal_event WHERE org_id=%s AND project_id=%s AND proposal_id=%s",
                        (*scope.key, row["proposal_id"])).fetchone():
            raise GuardActivationBlocked("GUARD_PROPOSAL_WITHDRAWN")
        if row["expires_at"] <= conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]:
            raise GuardActivationBlocked("GUARD_PROPOSAL_EXPIRED")
        return (members[0]["role"],)


def propose_guard_activation(principal, candidate, *, expected_version, idempotency_key, expires_at,
                             connect_factory=None):
    """Internal service; the external adapter must authenticate each OIDC request."""
    from aos_api.aip_action_policy import classify_action_risk
    from aos_api.aip_action_store import AipActionStore
    from aos_api.auth import Principal
    from aos_api.db import connect
    from aos_api.ecommerce_growth_host_ports import HostTransaction
    from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
    if (type(principal) is not Principal or principal.token_kind != "oidc"
            or type(principal.subject) is not str or not principal.subject
            or not principal.subject.isprintable() or principal.subject != principal.subject.strip()
            or type(candidate) not in _SPECS or type(expected_version) is not int or expected_version < 1
            or type(idempotency_key) is not str or not 1 <= len(idempotency_key) <= 120
            or idempotency_key != idempotency_key.strip()
            or type(expires_at) is not datetime or expires_at.tzinfo is None):
        raise GuardActivationBlocked("GUARD_MAKER_INPUT_INVALID")
    scope = TenantScope(principal.org_id, principal.project_id)
    guard = GuardPolicyActivationGuard(scope=scope, actor=principal.subject, candidate=candidate,
                                       expected_version=expected_version, expires_at=expires_at)
    with (connect_factory or connect)(scope) as conn:
        snapshot = guard.read_metadata(conn)
        body = guard.request(conn)
        risk = classify_action_risk(body.action_type_id, snapshot, body.payload, None)
        factory = TransactionBoundConnectFactory(HostTransaction(conn), scope)
        return AipActionStore(factory, guard_activation_guard=guard).create_proposal(
            scope, principal.subject, idempotency_key, body, snapshot, risk)


def decide_guard_activation(principal, proposal_id, idempotency_key, body, *, connect_factory):
    """Private issuer operation; outer commit follows a database-clock expiry check."""
    from aos_api.aip_action_models import DecideActionProposalRequest
    from aos_api.aip_action_store import AipActionStore
    from aos_api.auth import Principal
    from aos_api.ecommerce_growth_host_ports import HostTransaction
    from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
    if (type(principal) is not Principal or principal.token_kind != "oidc"
            or type(body) is not DecideActionProposalRequest or not callable(connect_factory)):
        raise GuardActivationBlocked("GUARD_ISSUER_SERVICE_REQUIRED")
    scope = TenantScope(principal.org_id, principal.project_id)
    guard = GuardPolicyApprovalGuard(scope=scope, checker=principal.subject)
    with connect_factory(scope) as conn:
        factory = TransactionBoundConnectFactory(HostTransaction(conn), scope)
        result = AipActionStore(factory, guard_approval_guard=guard).decide(
            scope, principal.subject, proposal_id, idempotency_key, body)
        event = conn.execute(
            "SELECT e.expires_at,p.expires_at AS proposal_expires FROM aip_action_approval_event e "
            "JOIN aip_action_proposal p USING(org_id,project_id,proposal_id) "
            "WHERE e.org_id=%s AND e.project_id=%s AND e.proposal_id=%s AND e.idempotency_key=%s "
            "AND e.actor_id=%s AND e.request_hash=%s",
            (*scope.key, proposal_id, idempotency_key, principal.subject,
             canonical_hash(body.model_dump(mode="json", by_alias=True)))).fetchone()
        now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        if not event or event["expires_at"] is None or min(event["expires_at"], event["proposal_expires"]) <= now:
            raise GuardActivationBlocked("GUARD_DECISION_EXPIRED_BEFORE_COMMIT")
        return result

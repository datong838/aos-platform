"""Signed guard policy maker and independent at-most-once approval issuer.

No credential fallback, Provider call, activation, or unknown-outcome resend.
The private attempt directory is persistent service state, not a temp cache.
"""
from contextlib import contextmanager
from datetime import datetime

from pydantic import Field, SecretStr, field_validator

from aos_api.aip_action_models import DecideActionProposalRequest
from aos_api.aip_contracts import AipContractModel
from aos_api.aip_guard_policy_activation import (
    GuardPolicyApprovalGuard, decide_guard_activation, propose_guard_activation,
)
from aos_api.aip_network_issuer_attempt import (
    AttemptAlreadyRecorded, AttemptReceipt, _reserve_attempt_receipt,
)
from aos_api.aip_network_issuer_auth import _require_external_oidc_config
from aos_api.aip_runtime_guard_policy_contracts import (
    EgressPolicyRevisionCreate, DataClassificationPolicyRevisionCreate,
)
from aos_api.aip_model_governance_policy_contracts import QuotaPolicyRevisionCreate
from aos_api.aip_runtime_guard_policy_store import canonical_hash
from aos_api.auth import Principal, resolve_principal
from aos_api.tenant_scope import TenantScope


class GuardIssuerBlocked(ValueError):
    pass


class _SignedGuardRequest(AipContractModel):
    org_id: str = Field(min_length=1, max_length=120)
    project_id: str = Field(min_length=1, max_length=120)
    bearer_token: SecretStr
    idempotency_key: str = Field(min_length=1, max_length=120)

    @field_validator("org_id", "project_id", "idempotency_key")
    @classmethod
    def _canonical(cls, value):
        if value != value.strip() or not value.isprintable() or any(ch.isspace() for ch in value):
            raise ValueError("exact identifier required")
        return value

    @field_validator("bearer_token")
    @classmethod
    def _bounded_token(cls, value):
        if not 1 <= len(value.get_secret_value()) <= 8192:
            raise ValueError("bounded external JWT required")
        return value


class GuardMakerCommand(_SignedGuardRequest):
    candidate: EgressPolicyRevisionCreate | DataClassificationPolicyRevisionCreate | QuotaPolicyRevisionCreate
    expected_version: int = Field(ge=1, strict=True)
    expires_at: datetime


class GuardDecisionCommand(_SignedGuardRequest):
    proposal_id: str = Field(min_length=1, max_length=160)
    decision: DecideActionProposalRequest

    @field_validator("proposal_id")
    @classmethod
    def _proposal_id(cls, value):
        return cls._canonical(value)

    @property
    def request_hash(self):
        return canonical_hash(self.decision.model_dump(mode="json", by_alias=True))


def _authenticate(command, expected_type):
    try:
        if type(command) is not expected_type:
            raise ValueError("exact request required")
        # Revalidate mutated/model_construct DTOs. Never include token in exceptions.
        request = expected_type.model_validate(command.model_dump())
        _require_external_oidc_config()
        principal = resolve_principal(token=request.bearer_token.get_secret_value(),
            header_org=request.org_id, header_project=request.project_id)
        if (type(principal) is not Principal or principal.token_kind != "oidc"
                or (principal.org_id, principal.project_id) != (request.org_id, request.project_id)
                or not principal.subject or principal.subject == "unknown"
                or principal.subject != principal.subject.strip() or not principal.subject.isprintable()):
            raise ValueError("exact external identity required")
        return request, principal, TenantScope(principal.org_id, principal.project_id)
    except Exception:
        raise GuardIssuerBlocked("GUARD_EXTERNAL_IDENTITY_REQUIRED") from None


def propose_guard_signed(command, *, connect_factory=None):
    c, principal, _ = _authenticate(command, GuardMakerCommand)
    return propose_guard_activation(principal, c.candidate, expected_version=c.expected_version,
        idempotency_key=c.idempotency_key, expires_at=c.expires_at, connect_factory=connect_factory)


class GuardPolicyIssuer:
    def __init__(self, connect_factory, attempt_directory, *, expected_database):
        if not callable(connect_factory) or type(expected_database) is not str or not expected_database:
            raise GuardIssuerBlocked("GUARD_PRIVATE_ISSUER_CONFIGURATION_REQUIRED")
        self._connect, self._attempt_directory = connect_factory, attempt_directory
        self._database = expected_database

    def _identity(self, conn, scope, read_only):
        row = conn.execute("""SELECT session_user AS login,current_user AS role,current_database() AS db,
          current_setting('aos.org_id',true) AS org,current_setting('aos.project_id',true) AS project,
          current_setting('transaction_isolation') AS isolation,
          EXISTS(SELECT 1 FROM pg_roles WHERE rolname=session_user AND
            (NOT rolcanlogin OR rolinherit OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)) AS unsafe,
          EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid=session_user::regrole
            OR (member=session_user::regrole AND (roleid<>'aos_runtime'::regrole OR admin_option))) AS extra_roles""").fetchone()
        if (not row or row["login"] != "aos_guard_approval_issuer" or row["role"] != "aos_runtime"
                or row["db"] != self._database or (row["org"], row["project"]) != scope.key
                or row["unsafe"] or row["extra_roles"] or conn.read_only is not read_only
                or row["isolation"] != ("repeatable read" if read_only else "serializable")):
            raise GuardIssuerBlocked("GUARD_DATABASE_IDENTITY_REQUIRED")

    @contextmanager
    def _decision_connect(self, scope):
        with self._connect(scope, False) as conn:
            self._identity(conn, scope, False)
            yield conn

    def _preflight(self, c, principal, scope):
        try:
            with self._decision_connect(scope) as conn:
                row = conn.execute("SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s "
                    "AND proposal_id=%s FOR UPDATE", (*scope.key, c.proposal_id)).fetchone()
                if (not row or row["version"] != c.decision.expected_proposal_version
                        or row["proposal_hash"] != c.decision.expected_proposal_hash):
                    raise GuardIssuerBlocked("GUARD_PROPOSAL_DRIFTED")
                GuardPolicyApprovalGuard(scope=scope, checker=principal.subject).check(
                    conn, scope, principal.subject, row)
        except GuardIssuerBlocked:
            raise
        except Exception:
            raise GuardIssuerBlocked("GUARD_CURRENT_CHECKER_OR_SOURCE_REQUIRED") from None

    def _inquire(self, c, principal, scope):
        with self._connect(scope, True) as conn:
            self._identity(conn, scope, True)
            members = conn.execute("SELECT role FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s",
                                   (*scope.key, principal.subject)).fetchall()
            if len(members) != 1 or members[0]["role"].lower() not in {"owner", "admin"}:
                raise GuardIssuerBlocked("GUARD_CURRENT_CHECKER_REQUIRED")
            row = conn.execute("""SELECT e.*,p.action_type_id,p.created_by AS maker,
                p.action_binding_hash AS binding,p.approval_policy_hash AS policy_hash,
                p.proposal_hash AS current_hash,d.snapshot
                FROM aip_action_approval_event e JOIN aip_action_proposal p USING(org_id,project_id,proposal_id)
                JOIN aip_action_draft d USING(org_id,project_id,proposal_id)
                WHERE e.org_id=%s AND e.project_id=%s AND e.idempotency_key=%s""",
                (*scope.key, c.idempotency_key)).fetchone()
            if row is None:
                return {"status": "unresolved", "activationAuthorized": False}
            if (row["action_type_id"] not in {"aip_activate_egress_policy", "aip_activate_data_policy", "aip_activate_quota_policy"}
                    or row["proposal_id"] != c.proposal_id or row["actor_id"] != principal.subject
                    or row["maker"] == principal.subject or row["request_hash"] != c.request_hash
                    or row["proposal_hash"] != c.decision.expected_proposal_hash
                    or row["current_hash"] != row["proposal_hash"]
                    or row["proposal_version"] != c.decision.expected_proposal_version
                    or row["decision"] != c.decision.decision.value
                    or row["action_binding_hash"] != row["binding"] or not row["binding"]
                    or row["approval_policy_hash"] != row["policy_hash"]
                    or canonical_hash(row["snapshot"]) != row["proposal_hash"]):
                raise GuardIssuerBlocked("GUARD_DECISION_RECEIPT_DRIFTED")
            return {"status": "observed", "proposalId": c.proposal_id,
                    "approvalEventId": row["approval_event_id"], "decision": row["decision"],
                    "activationAuthorized": False}

    def inquire(self, command):
        c, principal, scope = _authenticate(command, GuardDecisionCommand)
        return self._inquire(c, principal, scope)

    def execute(self, command):
        c, principal, scope = _authenticate(command, GuardDecisionCommand)
        # Existing exact Event is read-only history, never a second decision.
        existing = self._inquire(c, principal, scope)
        if existing["status"] == "observed":
            return existing
        receipt = AttemptReceipt(c.org_id, c.project_id, c.proposal_id, c.idempotency_key,
                                 c.request_hash, principal.subject)
        # Preflight has no writes. A prior durable attempt must never reach decide.
        self._preflight(c, principal, scope)
        try:
            _reserve_attempt_receipt(self._attempt_directory, receipt, namespace="guard-policy-issuer/v1")
        except AttemptAlreadyRecorded:
            return self._inquire(c, principal, scope)
        try:
            decide_guard_activation(principal, c.proposal_id, c.idempotency_key, c.decision,
                                    connect_factory=self._decision_connect)
        except Exception:
            # The outer commit may have succeeded before a connection failure.
            pass
        try:
            return self._inquire(c, principal, scope)
        except Exception:
            return {"status": "unresolved", "activationAuthorized": False}

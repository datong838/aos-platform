"""Owner-backed read-only proposal inquiry; never publication or approval."""
from aos_api.aip_budget_activation_store import (
    _identity, _member, _require_inquiry_connection,
    BudgetActivationDenied, BudgetActivationInquiryUnavailable,
)
from aos_api.aip_budget_contracts import BudgetRevision
from aos_api.aip_budget_policy_renewal_proposal import BudgetPolicyRenewalProposal
from aos_api.aip_model_governance_policy_contracts import BudgetPolicyRevision
from aos_api.aip_model_governance_policy_store import canonical_hash
from aos_api.aip_model_runtime_contracts import ProviderInstanceRevision
from aos_api.db import connect_read_only


class BudgetPolicyRenewalBlocked(ValueError):
    pass


def _content(model, *, provider=False):
    omit = {"tenant", "contentHash", "createdBy", "createdAt"}
    if provider:
        omit.add("revision")
    return {k: v for k, v in model.model_dump(mode="json", by_alias=True).items() if k not in omit}


def _exact(row, model, ref, scope, identity):
    if (row is None or type(row["revision"]) is not int
            or row["revision"] != ref.revision or row["lifecycle"] != "active"):
        raise BudgetPolicyRenewalBlocked("RENEWAL_REFERENCE_DRIFT")
    value = model.model_validate(row["payload"])
    provider = model is ProviderInstanceRevision
    if (value.tenant.org_id, value.tenant.project_id) != scope.key:
        raise BudgetPolicyRenewalBlocked("RENEWAL_REFERENCE_SCOPE")
    if (getattr(value, identity) != ref.asset_id or value.revision != ref.revision
            or value.content_hash != ref.content_hash or row["content_hash"] != ref.content_hash
            or value.lifecycle.value != "active"
            or canonical_hash(_content(value, provider=provider)) != ref.content_hash):
        raise BudgetPolicyRenewalBlocked("RENEWAL_REFERENCE_DRIFT")
    return value


class BudgetPolicyRenewalPreflight:
    def __init__(self, connect_factory=None):
        self._connect = connect_factory or connect_read_only

    def inquire(self, principal, proposal):
        scope, actor = _identity(principal)
        if type(proposal) is not BudgetPolicyRenewalProposal:
            raise BudgetPolicyRenewalBlocked("RENEWAL_EXACT_PROPOSAL_REQUIRED")
        p = BudgetPolicyRenewalProposal.model_validate(proposal.canonical_payload())
        if scope.key != (p.tenant.org_id, p.tenant.project_id) or actor != p.maker_subject:
            raise BudgetPolicyRenewalBlocked("RENEWAL_MAKER_SCOPE")
        try:
            with self._connect(scope) as conn:
                _require_inquiry_connection(conn, scope)
                unsafe = conn.execute("""SELECT EXISTS(
                    SELECT 1 FROM pg_roles WHERE rolname=session_user
                    AND (rolsuper OR rolbypassrls OR NOT rolcanlogin))
                OR NOT current_schemas(true) <@ ARRAY['pg_catalog','public']::name[] OR EXISTS(
                    SELECT 1 FROM pg_class WHERE relname IN
                    ('aip_model_governance_policy_head','aip_model_governance_policy_revision',
                     'aip_budget_head','aip_budget_revision','aip_provider_instance_head',
                     'aip_provider_instance_revision','meta_membership')
                    AND relnamespace='public'::regnamespace
                    AND relowner IN (session_user::regrole,current_user::regrole)) AS unsafe""").fetchone()
                if unsafe is None or unsafe["unsafe"] is not False:
                    raise BudgetPolicyRenewalBlocked("RENEWAL_READ_IDENTITY")
                _member(conn, scope, actor, label="MAKER", lock=False)
                _member(conn, scope, p.checker_subject, label="CHECKER", lock=False)
                row = conn.execute("""SELECT h.current_revision,h.version,r.payload,
                    r.content_hash,r.revision,r.lifecycle FROM public.aip_model_governance_policy_head h
                    JOIN public.aip_model_governance_policy_revision r USING(org_id,project_id,policy_kind,policy_id)
                    WHERE h.org_id=%s AND h.project_id=%s AND h.policy_kind='budget'
                    AND h.policy_id=%s AND r.revision=h.current_revision""",
                    (*scope.key, p.source_policy.policy_id)).fetchone()
                if (row is None or row["version"] != p.expected_head_version
                        or row["current_revision"] != p.source_policy.revision):
                    raise BudgetPolicyRenewalBlocked("RENEWAL_SOURCE_HEAD_DRIFT")
                source = BudgetPolicyRevision.model_validate(row["payload"])
                if (source != p.source_policy or row["content_hash"] != source.content_hash
                        or row["revision"] != source.revision or row["lifecycle"] != "active"
                        or canonical_hash(_content(source)) != source.content_hash):
                    raise BudgetPolicyRenewalBlocked("RENEWAL_SOURCE_DRIFT")
                budget_ref = source.budget_revision_ref
                row = conn.execute("""SELECT r.payload,r.content_hash,r.revision,r.lifecycle
                    FROM public.aip_budget_head h JOIN public.aip_budget_revision r USING(org_id,project_id,budget_id)
                    WHERE h.org_id=%s AND h.project_id=%s AND h.budget_id=%s
                    AND r.revision=h.current_revision""", (*scope.key, budget_ref.asset_id)).fetchone()
                budget = _exact(row, BudgetRevision, budget_ref, scope, "budget_id")
                now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
                target = p.target_policy
                if (not budget.effective_from <= now < budget.effective_until
                        or not target.effective_from <= now < target.effective_until
                        or target.effective_from < budget.effective_from
                        or target.effective_until > budget.effective_until
                        or not budget.hard_stop or budget.unknown_usage_behavior != "block"):
                    raise BudgetPolicyRenewalBlocked("RENEWAL_BUDGET_WINDOW")
                provider_ref = source.development_cost_authorization.provider
                row = conn.execute("""SELECT r.payload,r.content_hash,r.revision,r.lifecycle
                    FROM public.aip_provider_instance_head h
                    JOIN public.aip_provider_instance_revision r USING(org_id,project_id,provider_instance_id)
                    WHERE h.org_id=%s AND h.project_id=%s AND h.provider_instance_id=%s
                    AND r.revision=h.current_revision""", (*scope.key, provider_ref.asset_id)).fetchone()
                _exact(row, ProviderInstanceRevision, provider_ref, scope, "provider_instance_id")
                return {"status": "observed", "proposalHash": p.proposal_hash,
                        "sourcePolicyRevision": source.revision, "sourceHeadVersion": p.expected_head_version,
                        "budgetRef": budget_ref.model_dump(mode="json", by_alias=True),
                        "providerRef": provider_ref.model_dump(mode="json", by_alias=True),
                        "activationEligible": False, "approvalVerified": False}

        except BudgetPolicyRenewalBlocked:
            raise
        except (BudgetActivationDenied, BudgetActivationInquiryUnavailable) as exc:
            raise BudgetPolicyRenewalBlocked(str(exc)) from None
        except Exception:
            # Do not expose native payloads, connection details or credentials.
            raise BudgetPolicyRenewalBlocked("RENEWAL_OWNER_READ_UNAVAILABLE") from None

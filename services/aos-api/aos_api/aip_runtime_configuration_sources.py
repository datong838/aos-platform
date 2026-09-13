"""AIP-owned configuration-source adapters for extension runtime admission.

These readers only prove that an exact reference is the tenant's current,
usable revision in the original AIP authority.  They do not grant execution or
copy policy contents into the extension-runtime domain.
"""
from aos_api.aip_model_runtime_contracts import ModelRuntimeLifecycle, RuntimePolicyRevision
from aos_api.aip_model_runtime_store import canonical_hash as runtime_policy_hash
from aos_api.aip_network_policy_contracts import NetworkPolicyRevision
from aos_api.aip_network_policy_store import canonical_hash as network_policy_hash
from aos_api.aip_runtime_guard_policy_contracts import (
    DataClassificationPolicyRevision,
    EgressPolicyRevision,
    GuardPolicyLifecycle,
)
from aos_api.aip_runtime_guard_policy_store import canonical_hash as guard_policy_hash
from aos_api.aip_model_governance_policy_contracts import (
    BudgetPolicyRevision,
    ModelGovernancePolicyLifecycle,
    QuotaPolicyRevision,
)
from aos_api.aip_model_governance_policy_store import canonical_hash as governance_policy_hash
from aos_api.aip_runtime_configuration_authority import read_current_budget_ref
from aos_api.aip_production_contracts import BriefLifecycle, CreateResponsibilityPlanRequest
from aos_api.aip_production_contract_store import canonical_hash as production_contract_hash

from aos_api.extension_runtime.configuration_contracts import ConfigurationDocument, ConfigurationSourceRef
from aos_api.extension_runtime.configuration_authorization import (
    ConfigurationAuthorization,
    CurrentConfigurationPermission,
    _mint_current_four_source_authorization,
)
from aos_api.extension_runtime.lifecycle_store import _require_transaction, _values


DATA_AUTHORITY = "aip.data_classification_policy_revision"
POLICY_AUTHORITY = "aip.runtime_policy_revision"
NETWORK_AUTHORITY = "aip.network_policy_revision"
EGRESS_AUTHORITY = "aip.egress_policy_revision"
QUOTA_AUTHORITY = "aip.quota_policy_revision"
BUDGET_POLICY_AUTHORITY = "aip.budget_policy_revision"
ROLE_AUTHORITY = "aip.responsibility_plan_revision"


def assemble_current_configuration(conn, *, org_id, project_id, policy_ref, role_refs):
    """Assemble current source references; never persist or grant execution.

    The caller owns the short runtime transaction and must reauthorize any
    subsequent registration or execution. No policy identifiers are inferred.
    """
    scope = _current_scope(conn, org_id, project_id)
    if type(role_refs) is not tuple or not 1 <= len(role_refs) <= 64:
        raise ValueError("one to sixty-four exact responsibility references required")
    roles = tuple(_exact_ref(ref, purpose="role", expected_purpose="role",
                             authority=ROLE_AUTHORITY) for ref in role_refs)
    if len({ref.id for ref in roles}) != len(roles):
        raise ValueError("duplicate responsibility reference")
    value = _exact_ref(policy_ref, purpose="policy", expected_purpose="policy",
                       authority=POLICY_AUTHORITY)
    for ref in roles:
        read_current_responsibility_plan_ref(
            conn, org_id=org_id, project_id=project_id, purpose="role", ref=ref,
        )
    policy = _load_runtime_policy(conn, scope, value)
    budget_policy = _load_governance_policy(
        conn, scope, _asset_ref(policy.budget_policy_ref, BUDGET_POLICY_AUTHORITY),
        kind="budget", model=BudgetPolicyRevision,
    )
    document = ConfigurationDocument(
        roleRefs=roles,
        dataRefs=(_asset_ref(policy.data_classification_policy_ref, DATA_AUTHORITY),),
        budgetRef=_asset_ref(budget_policy.budget_revision_ref, "aip.budget_revision"),
        policyRef=value,
    )
    read_current_runtime_policy_ref(
        conn, org_id=org_id, project_id=project_id, purpose="policy", ref=value,
        configuration=document,
    )
    return document


def _current_scope(conn, org_id, project_id):
    _require_transaction(conn)
    expected = (org_id, project_id)
    if any(type(value) is not str or not value or value != value.strip() for value in expected):
        raise ValueError("exact configuration-source tenant required")
    row = conn.execute(
        "SELECT current_user AS role,current_setting('aos.org_id',true) AS org_id, "
        "current_setting('aos.project_id',true) AS project_id"
    ).fetchone()
    if _values(row, ("role", "org_id", "project_id")) != ("aos_runtime", *expected):
        raise PermissionError("configuration-source runtime role or tenant differs")
    return expected


def _exact_ref(ref, *, purpose, expected_purpose, authority):
    if purpose != expected_purpose:
        raise ValueError("configuration-source purpose differs")
    value = ConfigurationSourceRef.model_validate(ref)
    if value.authority != authority:
        raise ValueError("configuration-source authority differs")
    return value


def _asset_ref(value, authority):
    return ConfigurationSourceRef(
        authority=authority,
        id=value.asset_id,
        revision=value.revision,
        hash=f"sha256:{value.content_hash}",
    )


def _canonical_payload(document, excluded):
    return {
        key: item
        for key, item in document.model_dump(mode="json", by_alias=True).items()
        if key not in excluded
    }


def _load_guard_policy(conn, scope, value, *, kind, model):
    row = conn.execute(
        """SELECT h.current_revision,r.content_hash,r.lifecycle,r.effective_from,
                  r.effective_until,r.payload
             FROM aip_runtime_guard_policy_head h
             JOIN aip_runtime_guard_policy_revision r
               ON r.org_id=h.org_id AND r.project_id=h.project_id
              AND r.policy_kind=h.policy_kind AND r.policy_id=h.policy_id
              AND r.revision=h.current_revision
            WHERE h.org_id=%s AND h.project_id=%s
              AND h.policy_kind=%s AND h.policy_id=%s
            FOR SHARE OF h""",
        (*scope, kind, value.id),
    ).fetchone()
    if row is None:
        raise LookupError(f"current {kind} policy unavailable")
    current_revision, content_hash, lifecycle, effective_from, effective_until, payload = _values(
        row,
        ("current_revision", "content_hash", "lifecycle", "effective_from", "effective_until", "payload"),
    )
    if current_revision != value.revision or value.hash != f"sha256:{content_hash}":
        raise ValueError(f"{kind} policy reference is not current and exact")
    if lifecycle != GuardPolicyLifecycle.ACTIVE.value:
        raise PermissionError(f"{kind} policy is not active")
    checked_at = _values(conn.execute("SELECT clock_timestamp() AS checked_at").fetchone(), ("checked_at",))[0]
    if checked_at < effective_from or checked_at >= effective_until:
        raise PermissionError(f"{kind} policy is not effective")
    document = model.model_validate(payload)
    canonical_content = _canonical_payload(document, {"tenant", "contentHash", "createdBy", "createdAt"})
    if (
        (document.tenant.org_id, document.tenant.project_id) != scope
        or document.policy_id != value.id
        or document.revision != value.revision
        or document.content_hash != content_hash
        or document.lifecycle.value != lifecycle
        or document.effective_from != effective_from
        or document.effective_until != effective_until
        or guard_policy_hash(canonical_content) != content_hash
    ):
        raise ValueError(f"{kind} policy payload differs from authority columns")
    return document


def _load_data_classification(conn, scope, value):
    return _load_guard_policy(
        conn, scope, value, kind="data_classification", model=DataClassificationPolicyRevision
    )


def read_current_data_classification_ref(conn, *, org_id, project_id, purpose, ref, **_context):
    """Validate an exact current, active and effective AIP data-policy ref."""
    scope = _current_scope(conn, org_id, project_id)
    value = _exact_ref(ref, purpose=purpose, expected_purpose="data", authority=DATA_AUTHORITY)
    _load_data_classification(conn, scope, value)
    return True


def read_current_responsibility_plan_ref(
    conn, *, org_id, project_id, purpose, ref, **_context
):
    """Validate one exact current and frozen AIP responsibility plan."""
    scope = _current_scope(conn, org_id, project_id)
    value = _exact_ref(ref, purpose=purpose, expected_purpose="role", authority=ROLE_AUTHORITY)
    row = conn.execute(
        """SELECT h.current_revision,r.plan_id,r.revision,r.profile,r.template_ref,
                  r.slots,r.merge_decisions,r.profile_recommendation_ref,
                  r.profile_confirmation_id,r.merge_policy_ref,
                  r.merge_decision_receipt_ids,r.content_hash,r.lifecycle
             FROM aip_responsibility_plan_head h
             JOIN aip_responsibility_plan_revision r
               ON r.org_id=h.org_id AND r.project_id=h.project_id
              AND r.plan_id=h.plan_id AND r.revision=h.current_revision
            WHERE h.org_id=%s AND h.project_id=%s AND h.plan_id=%s
            FOR SHARE OF h""",
        (*scope, value.id),
    ).fetchone()
    if row is None:
        raise LookupError("current responsibility plan unavailable")
    fields = (
        "current_revision", "plan_id", "revision", "profile", "template_ref", "slots",
        "merge_decisions", "profile_recommendation_ref", "profile_confirmation_id",
        "merge_policy_ref", "merge_decision_receipt_ids", "content_hash", "lifecycle",
    )
    (
        current_revision, plan_id, revision, profile, template_ref, slots,
        merge_decisions, recommendation_ref, confirmation_id, merge_policy_ref,
        merge_receipt_ids, content_hash, lifecycle,
    ) = _values(row, fields)
    if (
        current_revision != value.revision
        or revision != value.revision
        or plan_id != value.id
        or value.hash != f"sha256:{content_hash}"
    ):
        raise ValueError("responsibility plan reference is not current and exact")
    if lifecycle != BriefLifecycle.FROZEN.value:
        raise PermissionError("responsibility plan is not frozen")
    content = CreateResponsibilityPlanRequest.model_validate(
        {
            "profile": profile,
            "templateRef": template_ref,
            "slots": slots,
            "mergeDecisions": merge_decisions,
            "profileRecommendationRef": recommendation_ref,
            "profileConfirmationId": confirmation_id,
            "mergePolicyRef": merge_policy_ref,
            "mergeDecisionReceiptIds": merge_receipt_ids,
        }
    )
    if production_contract_hash(content.model_dump(mode="json", by_alias=True)) != content_hash:
        raise ValueError("responsibility plan payload differs from authority columns")
    return True


def read_current_configuration_budget_ref(
    conn, *, purpose, ref, org_id, project_id, **_context
):
    if purpose != "budget":
        raise ValueError("configuration-source purpose differs")
    read_current_budget_ref(conn, org_id=org_id, project_id=project_id, ref=ref)
    return True


def build_current_configuration_authorization(*, permission):
    """Build the AIP-owned exact reader set for runtime configuration admission."""
    readers = {
        ("role", ROLE_AUTHORITY): read_current_responsibility_plan_ref,
        ("data", DATA_AUTHORITY): read_current_data_classification_ref,
        ("budget", "aip.budget_revision"): read_current_configuration_budget_ref,
        ("policy", POLICY_AUTHORITY): read_current_runtime_policy_ref,
    }
    if type(permission) is CurrentConfigurationPermission:
        return _mint_current_four_source_authorization(permission=permission)
    return ConfigurationAuthorization(permission=permission, readers=readers)


def _load_network_policy(conn, scope, value):
    row = conn.execute(
        """SELECT h.current_revision,r.content_hash,r.lifecycle,r.effective_from,
                  r.effective_until,r.payload
             FROM aip_network_policy_head h
             JOIN aip_network_policy_revision r
               ON r.org_id=h.org_id AND r.project_id=h.project_id
              AND r.policy_id=h.policy_id AND r.revision=h.current_revision
            WHERE h.org_id=%s AND h.project_id=%s AND h.policy_id=%s
            FOR SHARE OF h""",
        (*scope, value.id),
    ).fetchone()
    if row is None:
        raise LookupError("current network policy unavailable")
    current_revision, content_hash, lifecycle, effective_from, effective_until, payload = _values(
        row, ("current_revision", "content_hash", "lifecycle", "effective_from", "effective_until", "payload")
    )
    if current_revision != value.revision or value.hash != f"sha256:{content_hash}":
        raise ValueError("network policy reference is not current and exact")
    if lifecycle != GuardPolicyLifecycle.ACTIVE.value:
        raise PermissionError("network policy is not active")
    checked_at = _values(conn.execute("SELECT clock_timestamp() AS checked_at").fetchone(), ("checked_at",))[0]
    if checked_at < effective_from or checked_at >= effective_until:
        raise PermissionError("network policy is not effective")
    document = NetworkPolicyRevision.model_validate(payload)
    if (
        (document.tenant.org_id, document.tenant.project_id) != scope
        or document.policy_id != value.id
        or document.revision != value.revision
        or document.content_hash != content_hash
        or document.lifecycle.value != lifecycle
        or document.effective_from != effective_from
        or document.effective_until != effective_until
        or network_policy_hash(
            _canonical_payload(document, {"tenant", "contentHash", "createdBy", "createdAt"})
        ) != content_hash
    ):
        raise ValueError("network policy payload differs from authority columns")
    return document


def _load_governance_policy(conn, scope, value, *, kind, model):
    row = conn.execute(
        """SELECT h.current_revision,r.content_hash,r.lifecycle,r.effective_from,
                  r.effective_until,r.payload
             FROM aip_model_governance_policy_head h
             JOIN aip_model_governance_policy_revision r
               ON r.org_id=h.org_id AND r.project_id=h.project_id
              AND r.policy_kind=h.policy_kind AND r.policy_id=h.policy_id
              AND r.revision=h.current_revision
            WHERE h.org_id=%s AND h.project_id=%s
              AND h.policy_kind=%s AND h.policy_id=%s
            FOR SHARE OF h""",
        (*scope, kind, value.id),
    ).fetchone()
    if row is None:
        raise LookupError(f"current {kind} policy unavailable")
    current_revision, content_hash, lifecycle, effective_from, effective_until, payload = _values(
        row, ("current_revision", "content_hash", "lifecycle", "effective_from", "effective_until", "payload")
    )
    if current_revision != value.revision or value.hash != f"sha256:{content_hash}":
        raise ValueError(f"{kind} policy reference is not current and exact")
    if lifecycle != ModelGovernancePolicyLifecycle.ACTIVE.value:
        raise PermissionError(f"{kind} policy is not active")
    checked_at = _values(conn.execute("SELECT clock_timestamp() AS checked_at").fetchone(), ("checked_at",))[0]
    if checked_at < effective_from or checked_at >= effective_until:
        raise PermissionError(f"{kind} policy is not effective")
    document = model.model_validate(payload)
    if (
        (document.tenant.org_id, document.tenant.project_id) != scope
        or document.policy_id != value.id
        or document.revision != value.revision
        or document.content_hash != content_hash
        or document.lifecycle.value != lifecycle
        or document.effective_from != effective_from
        or document.effective_until != effective_until
        or governance_policy_hash(
            _canonical_payload(document, {"tenant", "contentHash", "createdBy", "createdAt"})
        ) != content_hash
    ):
        raise ValueError(f"{kind} policy payload differs from authority columns")
    return document


def _load_runtime_policy(conn, scope, value):
    row = conn.execute(
        """SELECT h.current_revision,r.content_hash,r.lifecycle,r.payload
             FROM aip_runtime_policy_head h
             JOIN aip_runtime_policy_revision r
               ON r.org_id=h.org_id AND r.project_id=h.project_id
              AND r.runtime_policy_id=h.runtime_policy_id
              AND r.revision=h.current_revision
            WHERE h.org_id=%s AND h.project_id=%s AND h.runtime_policy_id=%s
            FOR SHARE OF h""",
        (*scope, value.id),
    ).fetchone()
    if row is None:
        raise LookupError("current runtime policy unavailable")
    current_revision, content_hash, lifecycle, payload = _values(
        row, ("current_revision", "content_hash", "lifecycle", "payload")
    )
    if current_revision != value.revision or value.hash != f"sha256:{content_hash}":
        raise ValueError("runtime policy reference is not current and exact")
    if lifecycle != ModelRuntimeLifecycle.ACTIVE.value:
        raise PermissionError("runtime policy is not active")
    document = RuntimePolicyRevision.model_validate(payload)
    canonical_content = _canonical_payload(
        document, {"tenant", "revision", "contentHash", "createdBy", "createdAt"}
    )
    if (
        (document.tenant.org_id, document.tenant.project_id) != scope
        or document.policy_id != value.id
        or document.revision != value.revision
        or document.content_hash != content_hash
        or document.lifecycle.value != lifecycle
        or runtime_policy_hash(canonical_content) != content_hash
    ):
        raise ValueError("runtime policy payload differs from authority columns")
    if document.kill_switch_enabled:
        raise PermissionError("runtime policy kill switch is enabled")
    return document


def read_current_runtime_policy_ref(
    conn, *, org_id, project_id, purpose, ref, configuration=None, **_context
):
    """Validate a runtime policy, all current dependencies and configuration bindings."""
    scope = _current_scope(conn, org_id, project_id)
    value = _exact_ref(ref, purpose=purpose, expected_purpose="policy", authority=POLICY_AUTHORITY)
    configuration = ConfigurationDocument.model_validate(configuration)
    policy = _load_runtime_policy(conn, scope, value)
    network_ref = _asset_ref(policy.network_policy_ref, NETWORK_AUTHORITY)
    egress_ref = _asset_ref(policy.egress_policy_ref, EGRESS_AUTHORITY)
    data_ref = _asset_ref(policy.data_classification_policy_ref, DATA_AUTHORITY)
    quota_ref = _asset_ref(policy.quota_policy_ref, QUOTA_AUTHORITY)
    budget_policy_ref = _asset_ref(policy.budget_policy_ref, BUDGET_POLICY_AUTHORITY)
    network = _load_network_policy(conn, scope, network_ref)
    egress = _load_guard_policy(conn, scope, egress_ref, kind="egress", model=EgressPolicyRevision)
    data = _load_data_classification(conn, scope, data_ref)
    quota = _load_governance_policy(conn, scope, quota_ref, kind="quota", model=QuotaPolicyRevision)
    budget_policy = _load_governance_policy(
        conn, scope, budget_policy_ref, kind="budget", model=BudgetPolicyRevision
    )
    if _asset_ref(network.egress_policy_ref, EGRESS_AUTHORITY) != egress_ref:
        raise PermissionError("network policy egress binding differs from runtime policy")
    bound_data = tuple(item for item in configuration.dataRefs if item.authority == DATA_AUTHORITY)
    if bound_data != (data_ref,):
        raise PermissionError("configuration data policy binding differs from runtime policy")
    budget_ref = _asset_ref(budget_policy.budget_revision_ref, "aip.budget_revision")
    if configuration.budgetRef != budget_ref:
        raise PermissionError("configuration budget binding differs from runtime policy")
    budget = read_current_budget_ref(
        conn, org_id=org_id, project_id=project_id, ref=configuration.budgetRef
    )
    # A later head lock can outlive an earlier dependency's validity window.
    # Re-sample database time only after every mutable head has been locked.
    checked_at = _values(
        conn.execute("SELECT clock_timestamp() AS checked_at").fetchone(), ("checked_at",)
    )[0]
    for name, item in (
        ("network", network),
        ("egress", egress),
        ("data classification", data),
        ("quota", quota),
        ("budget policy", budget_policy),
        ("budget", budget),
    ):
        if checked_at < item.effective_from or checked_at >= item.effective_until:
            raise PermissionError(f"{name} policy expired during configuration authorization")
    return True

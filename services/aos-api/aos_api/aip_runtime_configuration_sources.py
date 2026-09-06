"""AIP-owned configuration-source adapters for extension runtime admission.

These readers only prove that an exact reference is the tenant's current,
usable revision in the original AIP authority.  They do not grant execution or
copy policy contents into the extension-runtime domain.
"""
from aos_api.aip_model_runtime_contracts import ModelRuntimeLifecycle, RuntimePolicyRevision
from aos_api.aip_model_runtime_store import canonical_hash as runtime_policy_hash
from aos_api.aip_runtime_guard_policy_contracts import (
    DataClassificationPolicyRevision,
    GuardPolicyLifecycle,
)
from aos_api.aip_runtime_guard_policy_store import canonical_hash as guard_policy_hash

from aos_api.extension_runtime.configuration_contracts import ConfigurationSourceRef
from aos_api.extension_runtime.lifecycle_store import _require_transaction, _values


DATA_AUTHORITY = "aip.data_classification_policy_revision"
POLICY_AUTHORITY = "aip.runtime_policy_revision"


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


def read_current_data_classification_ref(conn, *, org_id, project_id, purpose, ref, **_context):
    """Validate an exact current, active and effective AIP data-policy ref."""
    scope = _current_scope(conn, org_id, project_id)
    value = _exact_ref(ref, purpose=purpose, expected_purpose="data", authority=DATA_AUTHORITY)
    row = conn.execute(
        """SELECT h.current_revision,r.content_hash,r.lifecycle,r.effective_from,
                  r.effective_until,r.payload
             FROM aip_runtime_guard_policy_head h
             JOIN aip_runtime_guard_policy_revision r
               ON r.org_id=h.org_id AND r.project_id=h.project_id
              AND r.policy_kind=h.policy_kind AND r.policy_id=h.policy_id
              AND r.revision=h.current_revision
            WHERE h.org_id=%s AND h.project_id=%s
              AND h.policy_kind='data_classification' AND h.policy_id=%s
            FOR SHARE OF h""",
        (*scope, value.id),
    ).fetchone()
    if row is None:
        raise LookupError("current data-classification policy unavailable")
    current_revision, content_hash, lifecycle, effective_from, effective_until, payload = _values(
        row,
        ("current_revision", "content_hash", "lifecycle", "effective_from", "effective_until", "payload"),
    )
    if current_revision != value.revision or value.hash != f"sha256:{content_hash}":
        raise ValueError("data-classification policy reference is not current and exact")
    if lifecycle != GuardPolicyLifecycle.ACTIVE.value:
        raise PermissionError("data-classification policy is not active")
    # Read DB time only after FOR SHARE has returned: target expressions in the
    # locking SELECT may otherwise be evaluated before a lock wait.
    checked_at = _values(conn.execute("SELECT clock_timestamp() AS checked_at").fetchone(), ("checked_at",))[0]
    if checked_at < effective_from or checked_at >= effective_until:
        raise PermissionError("data-classification policy is not effective")
    document = DataClassificationPolicyRevision.model_validate(payload)
    canonical_payload = document.model_dump(mode="json", by_alias=True)
    canonical_content = {
        key: item for key, item in canonical_payload.items()
        if key not in {"tenant", "contentHash", "createdBy", "createdAt"}
    }
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
        raise ValueError("data-classification policy payload differs from authority columns")
    return True


def read_current_runtime_policy_ref(conn, *, org_id, project_id, purpose, ref, **_context):
    """Validate an exact current, active AIP runtime-policy ref with kill switch off."""
    scope = _current_scope(conn, org_id, project_id)
    value = _exact_ref(ref, purpose=purpose, expected_purpose="policy", authority=POLICY_AUTHORITY)
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
    canonical_payload = document.model_dump(mode="json", by_alias=True)
    canonical_content = {
        key: item for key, item in canonical_payload.items()
        if key not in {"tenant", "revision", "contentHash", "createdBy", "createdAt"}
    }
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
    return True

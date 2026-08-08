"""Canonical, permanently reproducible M2 installation event evidence."""

from __future__ import annotations

from datetime import UTC, datetime

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.composition_contracts import InstallationEventEvidence

EVIDENCE_SCHEMA_VERSION = "m2-installation-evidence/v1"
_TRANSITIONS = {
    "dry_apply": ("approved", "applied"),
    "verification": ("applied", "active"),
    "rollback": ("active", "rolled_back"),
    "uninstall": ("active", "uninstalled"),
}


def format_evidence_timestamp(value: datetime) -> str:
    """Render UTC with a required +00:00 suffix and trimmed microsecond zeros."""

    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("evidence timestamp must be timezone-aware")
    normalized = value.astimezone(UTC)
    base = normalized.strftime("%Y-%m-%dT%H:%M:%S")
    if normalized.microsecond:
        fraction = f"{normalized.microsecond:06d}".rstrip("0")
        base = f"{base}.{fraction}"
    return f"{base}+00:00"


def build_evidence_basis(
    *,
    evidence_type: str,
    installation_id: str,
    from_revision: int,
    to_revision: int,
    lock_hash: str,
    permission_diff_hash: str,
    migration_plan_hash: str,
    contribution_diff_hash: str,
    decision_id: str,
    observed_at: datetime,
) -> dict[str, object]:
    try:
        from_state, to_state = _TRANSITIONS[evidence_type]
    except KeyError as exc:
        raise ValueError("unsupported installation evidence type") from exc
    evidence_ref = (
        "evidence://bundle-installations/"
        f"{installation_id}/revisions/{to_revision}/{evidence_type}"
    )
    return {
        "schemaVersion": EVIDENCE_SCHEMA_VERSION,
        "type": evidence_type,
        "evidenceRef": evidence_ref,
        "installationId": installation_id,
        "fromRevision": from_revision,
        "toRevision": to_revision,
        "fromState": from_state,
        "toState": to_state,
        "lockHash": lock_hash,
        "permissionDiffHash": permission_diff_hash,
        "migrationPlanHash": migration_plan_hash,
        "contributionDiffHash": contribution_diff_hash,
        "decisionId": decision_id,
        "status": "valid",
        "observedAt": format_evidence_timestamp(observed_at),
    }


def build_event_evidence(**kwargs) -> InstallationEventEvidence:
    basis = build_evidence_basis(**kwargs)
    return InstallationEventEvidence.model_validate(
        {
            "type": basis["type"],
            "evidenceRef": basis["evidenceRef"],
            "evidenceHash": canonical_sha256(basis),
            "status": "valid",
            "observedAt": kwargs["observed_at"],
        }
    )


def verify_event_evidence(
    evidence: InstallationEventEvidence,
    **kwargs,
) -> None:
    evidence = InstallationEventEvidence.model_validate(evidence)
    basis = build_evidence_basis(evidence_type=evidence.type, **kwargs)
    if (
        evidence.evidence_ref != basis["evidenceRef"]
        or evidence.status != "valid"
        or format_evidence_timestamp(evidence.observed_at) != basis["observedAt"]
        or evidence.evidence_hash != canonical_sha256(basis)
    ):
        raise ValueError("installation event evidence failed integrity verification")

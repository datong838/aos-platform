"""Shared, side-effect-free release eligibility policy for Registry versions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from aos_api.asset_registry.canonical_json import canonical_json, canonical_sha256
from aos_api.asset_registry.contracts import (
    SHA256_PATTERN,
    BundleEvidence,
    BundleEvidenceStatus,
    BundleEvidenceType,
    BundleManifest,
    BundleSignature,
    BundleVersionStatus,
)
from aos_api.asset_registry.errors import (
    ManifestInvalidError,
    SignatureInvalidError,
    TrustRootUnavailableError,
    VerificationFailedError,
)
from aos_api.asset_registry.signature import (
    TrustRoot,
    TrustRootConfigurationError,
    TrustRootProvider,
    is_trust_root_current,
    verify_ed25519,
)

REQUIRED_RELEASE_EVIDENCE = (
    BundleEvidenceType.MANIFEST_VALIDATION,
    BundleEvidenceType.CONTENT_HASH,
    BundleEvidenceType.SIGNATURE_VERIFICATION,
    BundleEvidenceType.SBOM,
    BundleEvidenceType.BUNDLE_EVALS,
)


class ReleaseVersionRecord(Protocol):
    """Minimum persisted version shape consumed by the shared policy."""

    publisher: str
    manifest: BundleManifest
    content_hash: str
    signature: BundleSignature | None
    status: BundleVersionStatus
    evidence: list[BundleEvidence]
    artifacts: list[dict[str, object]]
    persisted_manifest: dict[str, object] | None


@dataclass(frozen=True)
class ReleasePolicyResult:
    """Canonical release identifiers safe to embed in a Registry snapshot."""

    signature_fingerprint: str
    release_evidence_revision: str


class ReleasePolicy:
    """Validate release evidence and the current publisher trust root."""

    def __init__(self, *, trust_roots: TrustRootProvider | None) -> None:
        self._trust_roots = trust_roots

    def snapshot(self) -> ReleasePolicy:
        """Freeze one trust-root view for a complete Registry snapshot read."""

        snapshot = getattr(self._trust_roots, "snapshot", None)
        if not callable(snapshot):
            raise TrustRootUnavailableError(
                "publisher trust-root provider cannot create a stable snapshot",
                details={"retryable": False},
            )
        try:
            frozen_roots = snapshot()
        except Exception as exc:
            raise TrustRootUnavailableError(
                "publisher trust-root service is unavailable",
                details={"retryable": True},
            ) from exc
        if not callable(getattr(frozen_roots, "get_trust_root", None)):
            raise TrustRootUnavailableError(
                "publisher trust-root provider returned an invalid snapshot",
                details={"retryable": False},
            )
        return ReleasePolicy(trust_roots=frozen_roots)

    def evaluate_snapshot_candidate(
        self,
        record: ReleaseVersionRecord,
        *,
        checked_at: datetime,
    ) -> ReleasePolicyResult | None:
        """Return release identifiers, or exclude a well-formed stale candidate."""

        try:
            return self._evaluate(
                record,
                checked_at=checked_at,
                require_published=True,
                expected_signature_fingerprint=None,
                expected_evidence_revision=None,
                exclude_ineligible=True,
            )
        except _CandidateIneligible:
            return None

    def evaluate(
        self,
        record: ReleaseVersionRecord,
        *,
        checked_at: datetime,
        require_published: bool = True,
        expected_signature_fingerprint: str | None = None,
        expected_evidence_revision: str | None = None,
    ) -> ReleasePolicyResult:
        """Fail closed and return the canonical release identifiers."""

        return self._evaluate(
            record,
            checked_at=checked_at,
            require_published=require_published,
            expected_signature_fingerprint=expected_signature_fingerprint,
            expected_evidence_revision=expected_evidence_revision,
            exclude_ineligible=False,
        )

    def _evaluate(
        self,
        record: ReleaseVersionRecord,
        *,
        checked_at: datetime,
        require_published: bool,
        expected_signature_fingerprint: str | None,
        expected_evidence_revision: str | None,
        exclude_ineligible: bool,
    ) -> ReleasePolicyResult:
        """Shared M1/M2 implementation with an explicit snapshot disposition."""

        if not isinstance(checked_at, datetime) or checked_at.utcoffset() is None:
            raise VerificationFailedError("registry verification clock is invalid")
        if require_published and record.status != BundleVersionStatus.PUBLISHED:
            if exclude_ineligible:
                raise _CandidateIneligible
            raise VerificationFailedError(
                "bundle version is not eligible for release",
                details={"currentStatus": record.status.value},
            )
        if record.signature is None:
            raise SignatureInvalidError("bundle signature is missing")

        trust_root = self._get_trust_root(record)
        if exclude_ineligible:
            evidence_by_type = self._assert_snapshot_candidate(
                record,
                checked_at=checked_at,
                trust_root=trust_root,
            )
        else:
            evidence_by_type = self._assert_release_evidence(
                record,
                checked_at=checked_at,
            )
            self._assert_current_signature(
                record,
                checked_at=checked_at,
                trust_root=trust_root,
                signature_evidence=evidence_by_type[
                    BundleEvidenceType.SIGNATURE_VERIFICATION
                ],
            )

        signature_fingerprint = evidence_by_type[
            BundleEvidenceType.SIGNATURE_VERIFICATION
        ][0].artifact_hash
        release_evidence_revision = _release_evidence_revision(evidence_by_type)
        _assert_expected_hash(
            expected_signature_fingerprint,
            actual=signature_fingerprint,
            label="signature fingerprint",
            error_type=SignatureInvalidError,
        )
        _assert_expected_hash(
            expected_evidence_revision,
            actual=release_evidence_revision,
            label="release evidence revision",
            error_type=VerificationFailedError,
        )
        return ReleasePolicyResult(
            signature_fingerprint=signature_fingerprint,
            release_evidence_revision=release_evidence_revision,
        )

    def _get_trust_root(self, record: ReleaseVersionRecord) -> TrustRoot | None:
        if record.signature is None or self._trust_roots is None:
            return None
        try:
            return self._trust_roots.get_trust_root(
                publisher=record.publisher,
                key_id=record.signature.key_id,
            )
        except Exception as exc:
            raise TrustRootUnavailableError(
                "publisher trust-root service is unavailable",
                details={"retryable": True},
            ) from exc

    @staticmethod
    def _assert_release_evidence(
        record: ReleaseVersionRecord,
        *,
        checked_at: datetime,
    ) -> dict[BundleEvidenceType, list[BundleEvidence]]:
        by_type = _release_evidence_by_type(record)

        for evidence_type in REQUIRED_RELEASE_EVIDENCE:
            entries = by_type.get(evidence_type, [])
            is_valid = bool(entries) and all(
                _evidence_is_current(item, checked_at=checked_at) for item in entries
            )
            if evidence_type == BundleEvidenceType.CONTENT_HASH:
                is_valid = is_valid and all(
                    item.artifact_hash == record.content_hash for item in entries
                )
            if not is_valid:
                _raise_evidence_gate_error(evidence_type)
        return by_type

    def _assert_current_signature(
        self,
        record: ReleaseVersionRecord,
        *,
        checked_at: datetime,
        trust_root: TrustRoot | None,
        signature_evidence: list[BundleEvidence],
    ) -> None:
        if record.signature is None or self._trust_roots is None:
            raise SignatureInvalidError("publisher trust roots are unavailable")
        if trust_root is None:
            raise SignatureInvalidError("publisher trust root is unavailable")
        trust_root_revision = getattr(trust_root, "revision", None)
        if (
            not isinstance(trust_root_revision, str)
            or not trust_root_revision
            or trust_root_revision != trust_root_revision.strip()
        ):
            raise SignatureInvalidError("publisher trust root revision is invalid")

        descriptor = _verified_content_descriptor(record)
        if not verify_ed25519(
            payload=canonical_json(descriptor),
            signature_b64=record.signature.signature,
            publisher=record.publisher,
            key_id=record.signature.key_id,
            trust_roots=_SingleTrustRootProvider(trust_root),
            algorithm=record.signature.algorithm,
            verified_at=checked_at,
        ):
            raise SignatureInvalidError(
                "bundle signature is not valid under current trust"
            )

        if len(signature_evidence) != 1:
            raise SignatureInvalidError("bundle signature evidence must be unique")
        evidence = signature_evidence[0]
        signature_envelope_hash = canonical_sha256(
            record.signature.model_dump(mode="json", by_alias=True, exclude_none=False)
        )
        if evidence.artifact_hash != signature_envelope_hash:
            raise SignatureInvalidError(
                "bundle signature evidence does not match envelope"
            )
        if evidence.metadata.get("trustRootRevision") != trust_root_revision:
            raise SignatureInvalidError("bundle signature evidence trust root is stale")
        if evidence.expires_at != trust_root.not_after:
            raise SignatureInvalidError(
                "bundle signature evidence expiry is inconsistent"
            )

    def _assert_snapshot_candidate(
        self,
        record: ReleaseVersionRecord,
        *,
        checked_at: datetime,
        trust_root: TrustRoot | None,
    ) -> dict[BundleEvidenceType, list[BundleEvidence]]:
        if record.signature is None:
            raise SignatureInvalidError("bundle signature is missing")
        evidence_by_type = _release_evidence_by_type(record)
        signature_evidence = evidence_by_type.get(
            BundleEvidenceType.SIGNATURE_VERIFICATION,
            [],
        )
        if len(signature_evidence) > 1:
            raise SignatureInvalidError("bundle signature evidence must be unique")
        descriptor = _verified_content_descriptor(record)
        content_evidence = evidence_by_type.get(BundleEvidenceType.CONTENT_HASH, [])
        if any(item.artifact_hash != record.content_hash for item in content_evidence):
            raise ManifestInvalidError(
                "bundle manifest or content hash evidence is not valid and current",
                details={"evidenceType": BundleEvidenceType.CONTENT_HASH.value},
            )
        if not signature_evidence:
            raise _CandidateIneligible
        evidence = signature_evidence[0]
        if evidence.artifact_hash != canonical_sha256(
            record.signature.model_dump(mode="json", by_alias=True, exclude_none=False)
        ):
            raise SignatureInvalidError(
                "bundle signature evidence does not match envelope"
            )
        if trust_root is None:
            raise _CandidateIneligible
        trust_root_revision = getattr(trust_root, "revision", None)
        if (
            not isinstance(trust_root_revision, str)
            or not trust_root_revision
            or trust_root_revision != trust_root_revision.strip()
        ):
            raise TrustRootUnavailableError(
                "publisher trust-root configuration is invalid",
                details={"retryable": False},
            )
        try:
            root_is_current = is_trust_root_current(
                trust_root,
                publisher=record.publisher,
                key_id=record.signature.key_id,
                checked_at=checked_at,
            )
        except TrustRootConfigurationError as exc:
            raise TrustRootUnavailableError(
                "publisher trust-root configuration is invalid",
                details={"retryable": False},
            ) from exc
        if not root_is_current:
            raise _CandidateIneligible
        if evidence.metadata.get("trustRootRevision") != trust_root_revision:
            raise _CandidateIneligible
        if not verify_ed25519(
            payload=canonical_json(descriptor),
            signature_b64=record.signature.signature,
            publisher=record.publisher,
            key_id=record.signature.key_id,
            trust_roots=_SingleTrustRootProvider(trust_root),
            algorithm=record.signature.algorithm,
            verified_at=checked_at,
        ):
            raise SignatureInvalidError(
                "bundle signature is not valid under current trust"
            )
        if evidence.expires_at != trust_root.not_after:
            raise SignatureInvalidError(
                "bundle signature evidence expiry is inconsistent"
            )
        for evidence_type in REQUIRED_RELEASE_EVIDENCE:
            entries = evidence_by_type.get(evidence_type, [])
            if not entries or not all(
                _evidence_is_current(item, checked_at=checked_at) for item in entries
            ):
                raise _CandidateIneligible
        return evidence_by_type


def _verified_content_descriptor(record: ReleaseVersionRecord) -> dict[str, object]:
    """Return the signed descriptor, accepting only semantics-equivalent legacy JSON."""

    current_manifest = record.manifest.model_dump(
        mode="json", by_alias=True, exclude_none=False
    )
    current = {"manifest": current_manifest, "artifacts": record.artifacts}
    if canonical_sha256(current) == record.content_hash:
        return current

    persisted = getattr(record, "persisted_manifest", None)
    if not isinstance(persisted, dict):
        raise ManifestInvalidError("stored bundle content descriptor changed")
    try:
        normalized = BundleManifest.model_validate(persisted).model_dump(
            mode="json", by_alias=True, exclude_none=False
        )
    except Exception as exc:
        raise ManifestInvalidError("stored bundle content descriptor changed") from exc
    if normalized != current_manifest:
        raise ManifestInvalidError("stored bundle content descriptor changed")
    historical = {"manifest": persisted, "artifacts": record.artifacts}
    if canonical_sha256(historical) != record.content_hash:
        raise ManifestInvalidError("stored bundle content descriptor changed")
    return historical


class _SingleTrustRootProvider:
    def __init__(self, trust_root: TrustRoot) -> None:
        self._trust_root = trust_root

    def get_trust_root(self, *, publisher: str, key_id: str) -> TrustRoot | None:
        if (
            self._trust_root.publisher == publisher
            and self._trust_root.key_id == key_id
        ):
            return self._trust_root
        return None


class _CandidateIneligible(Exception):
    """Internal control flow for a well-formed but stale snapshot candidate."""


def _release_evidence_by_type(
    record: ReleaseVersionRecord,
) -> dict[BundleEvidenceType, list[BundleEvidence]]:
    by_type: dict[BundleEvidenceType, list[BundleEvidence]] = {}
    for evidence in record.evidence:
        if evidence.type in REQUIRED_RELEASE_EVIDENCE:
            by_type.setdefault(evidence.type, []).append(evidence)
    return by_type


def _evidence_is_current(
    evidence: BundleEvidence,
    *,
    checked_at: datetime,
) -> bool:
    return (
        evidence.status == BundleEvidenceStatus.VALID
        and evidence.observed_at <= checked_at
        and (evidence.expires_at is None or evidence.expires_at > checked_at)
        and evidence.revoked_at is None
    )


def _release_evidence_revision(
    evidence_by_type: dict[BundleEvidenceType, list[BundleEvidence]],
) -> str:
    evidence = [
        item
        for evidence_type in REQUIRED_RELEASE_EVIDENCE
        for item in evidence_by_type[evidence_type]
    ]
    evidence.sort(
        key=lambda item: (
            item.type.value,
            item.artifact_hash,
            item.observed_at,
            (0, "") if item.expires_at is None else (1, item.expires_at.isoformat()),
        )
    )
    payload = [
        item.model_dump(
            mode="json",
            by_alias=True,
            include={
                "type",
                "artifact_hash",
                "status",
                "observed_at",
                "expires_at",
                "revoked_at",
            },
            exclude_none=False,
        )
        for item in evidence
    ]
    return canonical_sha256(payload)


def _assert_expected_hash(
    expected: str | None,
    *,
    actual: str,
    label: str,
    error_type: type[SignatureInvalidError | VerificationFailedError],
) -> None:
    if expected is None:
        return
    if re.fullmatch(SHA256_PATTERN, expected) is None or expected != actual:
        raise error_type(f"bundle {label} is stale")


def _raise_evidence_gate_error(evidence_type: BundleEvidenceType) -> None:
    details = {"evidenceType": evidence_type.value}
    if evidence_type == BundleEvidenceType.SIGNATURE_VERIFICATION:
        raise SignatureInvalidError(
            "bundle signature evidence is not valid and current",
            details=details,
        )
    if evidence_type in {
        BundleEvidenceType.MANIFEST_VALIDATION,
        BundleEvidenceType.CONTENT_HASH,
    }:
        raise ManifestInvalidError(
            "bundle manifest or content hash evidence is not valid and current",
            details=details,
        )
    raise VerificationFailedError(
        "bundle release evidence is not valid and current",
        details=details,
    )

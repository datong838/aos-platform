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
    TrustRootProvider,
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


@dataclass(frozen=True)
class ReleasePolicyResult:
    """Canonical release identifiers safe to embed in a Registry snapshot."""

    signature_fingerprint: str
    release_evidence_revision: str


class ReleasePolicy:
    """Validate release evidence and the current publisher trust root."""

    def __init__(self, *, trust_roots: TrustRootProvider | None) -> None:
        self._trust_roots = trust_roots

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

        if not isinstance(checked_at, datetime) or checked_at.utcoffset() is None:
            raise VerificationFailedError("registry verification clock is invalid")
        if require_published and record.status != BundleVersionStatus.PUBLISHED:
            raise VerificationFailedError(
                "bundle version is not eligible for release",
                details={"currentStatus": record.status.value},
            )
        if record.signature is None:
            raise SignatureInvalidError("bundle signature is missing")

        trust_root = self._get_trust_root(record)
        evidence_by_type = self._assert_release_evidence(record, checked_at=checked_at)
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
        by_type: dict[BundleEvidenceType, list[BundleEvidence]] = {}
        for evidence in record.evidence:
            if evidence.type in REQUIRED_RELEASE_EVIDENCE:
                by_type.setdefault(evidence.type, []).append(evidence)

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

        descriptor = {
            "manifest": record.manifest.model_dump(
                mode="json", by_alias=True, exclude_none=False
            ),
            "artifacts": record.artifacts,
        }
        if canonical_sha256(descriptor) != record.content_hash:
            raise ManifestInvalidError("stored bundle content descriptor changed")
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

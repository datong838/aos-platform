"""Package-owned validation for host-authorized analyst source material.

The host remains the only owner of tenant-scoped EvidenceBundle, Disclosure,
freshness, revocation and marking reads.  This module has no I/O and grants no
permission; it rejects incomplete or drifted material before prompt assembly.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from typing import TYPE_CHECKING, Annotated, Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

if TYPE_CHECKING:
    from .sdk_ports import GrowthAnalysisSourcePort


Identity = Annotated[
    str,
    StringConstraints(strict=True, min_length=1, max_length=240, pattern=r"^\S(?:.*\S)?$"),
]
Digest = Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$")]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class AnalysisExactRef(_Strict):
    resource_type: Identity = Field(alias="resourceType")
    resource_id: Identity = Field(alias="resourceId")
    revision: Annotated[int, Field(strict=True, ge=1)]
    content_hash: Digest = Field(alias="contentHash")


class AnalysisDisclosureRequest(_Strict):
    evidence_ref: AnalysisExactRef = Field(alias="evidenceRef")
    purpose: Literal["source"]
    requested_level: Literal["l3"] = Field(alias="requestedLevel")
    task_id: Identity = Field(alias="taskId")


class AnalysisEvidenceGrant(_Strict):
    decision_id: Identity = Field(alias="decisionId")
    request: AnalysisDisclosureRequest


class AnalysisBundleSourceRequest(_Strict):
    bundle_ref: AnalysisExactRef = Field(alias="bundleRef")
    grants: list[AnalysisEvidenceGrant] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def _complete_grants(self) -> AnalysisBundleSourceRequest:
        if self.bundle_ref.resource_type != "EvidenceBundleRevision":
            raise ValueError("analysis source must reference an exact evidence bundle")
        tasks = {grant.request.task_id for grant in self.grants}
        evidence = [_ref_key(grant.request.evidence_ref) for grant in self.grants]
        decisions = [grant.decision_id for grant in self.grants]
        if len(tasks) != 1 or len(evidence) != len(set(evidence)) or len(decisions) != len(set(decisions)):
            raise ValueError("analysis source grants must be unique and same-task")
        if any(grant.request.evidence_ref.resource_type != "Evidence" or grant.request.evidence_ref.revision != 1 for grant in self.grants):
            raise ValueError("analysis source grants require exact Evidence revision one")
        return self


class AnalysisMaterialItem(_Strict):
    evidence_ref: AnalysisExactRef = Field(alias="evidenceRef")
    disclosure_ref: AnalysisExactRef = Field(alias="disclosureRef")
    expires_at: datetime = Field(alias="expiresAt")
    payload: dict[str, Any]

    @field_validator("expires_at", mode="before")
    @classmethod
    def _parse_aware(cls, value: datetime | str) -> datetime:
        if type(value) is str:
            value = datetime.fromisoformat(value)
        if not isinstance(value, datetime):
            raise ValueError("analysis disclosure expiry requires datetime")
        if value.utcoffset() is None:
            raise ValueError("analysis disclosure expiry requires timezone")
        return value


class AnalysisBundleMaterial(_Strict):
    bundle_ref: AnalysisExactRef = Field(alias="bundleRef")
    cutoff_at: datetime = Field(alias="cutoffAt")
    marking: list[Identity]
    items: list[AnalysisMaterialItem] = Field(min_length=1, max_length=100)

    @field_validator("cutoff_at", mode="before")
    @classmethod
    def _parse_cutoff(cls, value: datetime | str) -> datetime:
        if type(value) is str:
            value = datetime.fromisoformat(value)
        if not isinstance(value, datetime):
            raise ValueError("analysis source cutoff requires datetime")
        if value.utcoffset() is None:
            raise ValueError("analysis source cutoff requires timezone")
        return value

    @model_validator(mode="after")
    def _unique_markings(self) -> AnalysisBundleMaterial:
        if not self.marking or len(self.marking) != len(set(self.marking)):
            raise ValueError("analysis source markings must be non-empty and unique")
        return self


def _ref_key(ref: AnalysisExactRef) -> tuple[str, str, int, str]:
    return ref.resource_type, ref.resource_id, ref.revision, ref.content_hash


def _payload_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def validate_analysis_bundle_material(
    request: AnalysisBundleSourceRequest | dict[str, Any],
    material: AnalysisBundleMaterial | dict[str, Any],
    *,
    now: datetime,
    max_bytes: int,
) -> dict[str, Any]:
    """Return canonical prompt material only when the host result is complete.

    Authorization and source freshness are host duties.  ``now`` is supplied
    by that host and is used only to reject expired Disclosure decisions.
    """
    try:
        if now.utcoffset() is None or type(max_bytes) is not int or max_bytes < 1:
            raise ValueError()
        wanted = AnalysisBundleSourceRequest.model_validate(request)
        supplied = AnalysisBundleMaterial.model_validate(material)
        if supplied.bundle_ref != wanted.bundle_ref or supplied.cutoff_at > now:
            raise ValueError()
        grant_by_evidence = {
            _ref_key(grant.request.evidence_ref): grant for grant in wanted.grants
        }
        item_keys = [_ref_key(item.evidence_ref) for item in supplied.items]
        # Disclosure grants are an unordered authorization set.  The trusted
        # host returns items in the canonical EvidenceBundle order, which we
        # preserve without letting caller grant order rearrange the material.
        if set(item_keys) != set(grant_by_evidence) or len(item_keys) != len(set(item_keys)):
            raise ValueError()
        for item in supplied.items:
            grant = grant_by_evidence[_ref_key(item.evidence_ref)]
            if (
                item.evidence_ref.resource_type != "Evidence"
                or item.evidence_ref.revision != 1
                or item.disclosure_ref.resource_type != "EvidenceDisclosureDecision"
                or item.disclosure_ref.resource_id != grant.decision_id
                or item.expires_at <= now
                or _payload_hash(item.payload) != item.evidence_ref.content_hash
            ):
                raise ValueError()
        result = supplied.model_dump(mode="json", by_alias=True)
        encoded = json.dumps(
            result,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        if len(encoded) > max_bytes:
            raise ValueError()
        return result
    except (ValueError, TypeError, KeyError, RecursionError):
        raise ValueError("INVALID_ANALYSIS_SOURCE_MATERIAL") from None


def read_authorized_analysis_bundle(
    port: GrowthAnalysisSourcePort,
    *,
    task_id: str,
    actor: str,
    request: AnalysisBundleSourceRequest | Mapping[str, Any],
    markings: tuple[str, ...],
    now: datetime,
    max_source_age_seconds: int,
    max_bytes: int,
) -> dict[str, Any]:
    """Read once through the tenant-bound host, then validate its material."""
    try:
        read = getattr(port, "read", None)
        if (
            not callable(read)
            or type(task_id) is not str
            or not 1 <= len(task_id.strip()) <= 240
            or type(actor) is not str
            or not 1 <= len(actor.strip()) <= 240
            or type(markings) is not tuple
            or not markings
            or len(markings) != len(set(markings))
            or any(type(item) is not str or not 1 <= len(item.strip()) <= 120 for item in markings)
            or not isinstance(now, datetime)
            or now.utcoffset() is None
            or type(max_source_age_seconds) is not int
            or not 1 <= max_source_age_seconds <= 2_678_400
            or type(max_bytes) is not int
            or not 1 <= max_bytes <= 2_097_152
        ):
            raise ValueError()
        wanted = AnalysisBundleSourceRequest.model_validate(request)
    except (ValueError, TypeError, KeyError, RecursionError):
        raise ValueError("INVALID_ANALYSIS_SOURCE_PORT_REQUEST") from None

    material = read(
        task_id=task_id,
        actor=actor,
        request=wanted.model_dump(mode="json", by_alias=True),
        markings=markings,
        now=now,
        max_source_age_seconds=max_source_age_seconds,
        max_bytes=max_bytes,
    )
    if not isinstance(material, Mapping):
        raise ValueError("INVALID_ANALYSIS_SOURCE_MATERIAL")
    return validate_analysis_bundle_material(wanted, dict(material), now=now, max_bytes=max_bytes)


__all__ = [
    "AnalysisBundleMaterial",
    "AnalysisBundleSourceRequest",
    "AnalysisDisclosureRequest",
    "AnalysisEvidenceGrant",
    "AnalysisExactRef",
    "AnalysisMaterialItem",
    "read_authorized_analysis_bundle",
    "validate_analysis_bundle_material",
]

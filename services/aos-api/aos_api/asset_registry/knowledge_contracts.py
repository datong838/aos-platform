"""Strict contracts for governed knowledge assets exported by VerticalPack bundles."""

from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import ResourceRef
from aos_api.asset_registry.contracts import (
    BUNDLE_ID_PATTERN,
    CAPABILITY_PATTERN,
    SHA256_PATTERN,
    StrictContract,
    _require_exact_text,
    _require_relative_bundle_path,
)

KNOWLEDGE_PACKAGE_API_VERSION = "aos.dev/knowledge-package/v1alpha1"


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    payload: dict[str, object] = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError(f"knowledge package contains duplicate key {key!r}")
        payload[key] = value
    return payload


class KnowledgeLicenseDecision(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"
    UNKNOWN = "unknown"


class KnowledgePackageRollbackMode(StrEnum):
    REMOVE_PROJECTION_RETAIN_CANONICAL = "remove-projection-retain-canonical"


class KnowledgeSourceInventoryItem(StrictContract):
    source_id: str = Field(
        alias="sourceId", min_length=1, max_length=160, pattern=CAPABILITY_PATTERN
    )
    source_uri: str = Field(alias="sourceUri", min_length=1, max_length=2048)
    observed_at: datetime = Field(alias="observedAt")
    freshness_expires_at: datetime = Field(alias="freshnessExpiresAt")
    license_id: str = Field(alias="licenseId", min_length=1, max_length=200)
    usage_policy: str = Field(alias="usagePolicy", min_length=1, max_length=200)
    license_decision: KnowledgeLicenseDecision = Field(alias="licenseDecision")
    content_hash: str = Field(alias="contentHash", pattern=SHA256_PATTERN)
    provider: str = Field(min_length=1, max_length=200)
    provider_version: str = Field(alias="providerVersion", min_length=1, max_length=120)

    @field_validator("source_uri")
    @classmethod
    def _trusted_web_uri_shape(cls, value: str) -> str:
        value = _require_exact_text(value, label="knowledge source URI")
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("knowledge source URI must be an absolute HTTPS URL")
        if parsed.username or parsed.password or parsed.fragment:
            raise ValueError("knowledge source URI must not contain credentials or fragment")
        return value

    @field_validator("license_id", "usage_policy", "provider", "provider_version")
    @classmethod
    def _normalized_governance_text(cls, value: str) -> str:
        return _require_exact_text(value, label="knowledge source governance value")

    @field_validator("observed_at", "freshness_expires_at")
    @classmethod
    def _timezone_aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("knowledge source timestamps must include a timezone")
        return value

    @model_validator(mode="after")
    def _freshness_window(self) -> KnowledgeSourceInventoryItem:
        if self.freshness_expires_at <= self.observed_at:
            raise ValueError("freshnessExpiresAt must follow observedAt")
        return self


class KnowledgePackageEntry(StrictContract):
    entry_id: str = Field(
        alias="entryId", min_length=1, max_length=200, pattern=CAPABILITY_PATTERN
    )
    category: str = Field(min_length=1, max_length=120, pattern=CAPABILITY_PATTERN)
    payload_path: str = Field(alias="payloadPath", min_length=1, max_length=1024)
    payload_hash: str = Field(alias="payloadHash", pattern=SHA256_PATTERN)
    source_id: str = Field(
        alias="sourceId", min_length=1, max_length=160, pattern=CAPABILITY_PATTERN
    )
    subject: ResourceRef
    confidence: float = Field(ge=0.0, le=1.0)
    markings: list[str] = Field(min_length=1, max_length=32)
    applicability: list[str] = Field(min_length=1, max_length=64)
    owner_roles: list[str] = Field(alias="ownerRoles", min_length=1, max_length=32)

    @field_validator("payload_path")
    @classmethod
    def _safe_payload_path(cls, value: str) -> str:
        return _require_relative_bundle_path(value, label="knowledge payload path")

    @field_validator("markings", "applicability", "owner_roles")
    @classmethod
    def _unique_normalized_values(cls, values: list[str]) -> list[str]:
        checked = [
            _require_exact_text(value, label="knowledge entry scope value")
            for value in values
        ]
        if len(checked) != len(set(checked)):
            raise ValueError("knowledge entry scope values must be unique")
        return checked


class KnowledgePackageRollback(StrictContract):
    mode: KnowledgePackageRollbackMode
    receipt_required: Literal[True] = Field(alias="receiptRequired")


class KnowledgePackageManifest(StrictContract):
    api_version: Literal[KNOWLEDGE_PACKAGE_API_VERSION] = Field(alias="apiVersion")
    kind: Literal["KnowledgePackage"]
    package_id: str = Field(
        alias="packageId", min_length=1, max_length=160, pattern=BUNDLE_ID_PATTERN
    )
    package_version: str = Field(alias="packageVersion", min_length=1, max_length=120)
    source_inventory: list[KnowledgeSourceInventoryItem] = Field(
        alias="sourceInventory", min_length=1, max_length=10_000
    )
    entries: list[KnowledgePackageEntry] = Field(default_factory=list, max_length=10_000)
    rollback: KnowledgePackageRollback

    @field_validator("package_version")
    @classmethod
    def _normalized_version(cls, value: str) -> str:
        return _require_exact_text(value, label="knowledge package version")

    @model_validator(mode="after")
    def _closed_source_graph(self) -> KnowledgePackageManifest:
        source_ids = [source.source_id for source in self.source_inventory]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("knowledge source IDs must be unique")
        entry_ids = [entry.entry_id for entry in self.entries]
        if len(entry_ids) != len(set(entry_ids)):
            raise ValueError("knowledge entry IDs must be unique")
        known_sources = set(source_ids)
        if any(entry.source_id not in known_sources for entry in self.entries):
            raise ValueError("every knowledge entry must reference an inventoried source")
        payload_paths = [entry.payload_path for entry in self.entries]
        if len(payload_paths) != len(set(payload_paths)):
            raise ValueError("knowledge payload paths must be unique")
        return self

    def entry_by_id(self, entry_id: str) -> KnowledgePackageEntry:
        matches = [entry for entry in self.entries if entry.entry_id == entry_id]
        if len(matches) != 1:
            raise ValueError("knowledge package entry must resolve exactly once")
        return matches[0]

    def readiness_blockers(self, *, now: datetime) -> tuple[str, ...]:
        """Return stable fail-closed reasons without changing bundle authority."""

        blockers: list[str] = []
        for source in self.source_inventory:
            if source.license_decision is KnowledgeLicenseDecision.UNKNOWN:
                blockers.append(f"license_unknown:{source.source_id}")
            elif source.license_decision is KnowledgeLicenseDecision.DENIED:
                blockers.append(f"license_denied:{source.source_id}")
            if source.freshness_expires_at <= now:
                blockers.append(f"source_stale:{source.source_id}")
        return tuple(blockers)


def parse_knowledge_package_json(raw: bytes | str) -> KnowledgePackageManifest:
    """Parse serialized JSON without coercing Python callers or accepting duplicates."""

    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="strict")
    if not isinstance(raw, str):
        raise TypeError("knowledge package JSON must be bytes or text")
    parsed = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    if not isinstance(parsed, dict):
        raise ValueError("knowledge package JSON root must be an object")
    canonical_input = json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
    return KnowledgePackageManifest.model_validate_json(canonical_input)

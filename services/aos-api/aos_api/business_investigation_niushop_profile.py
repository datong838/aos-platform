"""Disabled Niushop semantic menu, database discovery and object mapping Profile."""

from __future__ import annotations

import hashlib
import json
from typing import Literal, Self

from pydantic import Field, model_validator

from aos_api.aip_contracts import AipContractModel
from aos_api.business_investigation_shared_contracts import InvestigationExactRef


PROFILE_SCHEMA = "aos.business-investigation.niushop-profile/v1"
ACCEPTANCE_SCHEMA = "aos.business-investigation.niushop-profile-acceptance/v1"
SHA256 = r"^sha256:[0-9a-f]{64}$"

NIUSHOP_SEMANTIC_FAMILIES = {
    "product", "sku", "inventory", "order", "payment", "refund", "customer", "member",
    "distribution", "promotion", "coupon", "experience_code", "commission", "content",
    "storefront", "admin_capability",
}
NIUSHOP_CANONICAL_TYPES = {
    "Product", "SKU", "InventoryPosition", "Order", "OrderLine", "Payment", "Refund",
    "Customer", "MemberAccount", "DistributionRelation", "Promotion", "Coupon",
    "ExperienceCode", "Commission", "ContentAsset", "StorefrontSection",
}
ALLOWED_SQL = {"SHOW", "DESCRIBE", "EXPLAIN", "SELECT"}
FORBIDDEN_SQL = {"INSERT", "UPDATE", "DELETE", "DDL", "LOCK", "SET_GLOBAL", "FILE", "PROCEDURE"}


def _canonical_hash(value: dict) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class NiushopMenuSemantic(AipContractModel):
    semantic_id: str = Field(min_length=1, max_length=120)
    fact_families: list[str] = Field(min_length=1, max_length=10)
    required_observations: list[str] = Field(min_length=1, max_length=10)
    requires_observation: Literal[True]


class NiushopDatabaseDomain(AipContractModel):
    domain_id: str = Field(min_length=1, max_length=120)
    pattern_hints: list[str] = Field(min_length=1, max_length=12)
    exploration_mode: Literal["metadata_then_bounded_select"]
    requires_discovery: Literal[True]
    physical_existence_verified: Literal[False]

    @model_validator(mode="after")
    def _patterns_are_non_authoritative(self) -> Self:
        if any(not value.startswith("*") or not value.endswith("*") for value in self.pattern_hints):
            raise ValueError("database pattern hints must remain wildcard discovery hints")
        return self


class NiushopObjectMapping(AipContractModel):
    mapping_id: str = Field(min_length=1, max_length=120)
    source_domains: list[str] = Field(min_length=1, max_length=10)
    canonical_types: list[str] = Field(min_length=1, max_length=10)
    canonical_facts: list[str] = Field(min_length=1, max_length=20)
    verification_required: Literal[True]
    hydration_allowed: Literal[False]


class NiushopReadOnlyDatabasePolicy(AipContractModel):
    connector_type: Literal["jdbc-mysql-ssh"]
    transport: Literal["ssh"]
    transaction_read_only: Literal[True]
    allowed_statements: list[str]
    forbidden_statements: list[str]
    max_rows: int = Field(ge=1, le=1000)
    query_timeout_seconds: int = Field(ge=1, le=30)
    schema_metadata_only_by_default: Literal[True]
    source_access_authorized: Literal[False]

    @model_validator(mode="after")
    def _read_only(self) -> Self:
        if set(self.allowed_statements) != ALLOWED_SQL or not FORBIDDEN_SQL <= set(self.forbidden_statements):
            raise ValueError("read-only SQL policy drifted")
        if set(self.allowed_statements) & set(self.forbidden_statements):
            raise ValueError("SQL allow and deny groups must be disjoint")
        return self


class NiushopProfile(AipContractModel):
    schema_version: str = PROFILE_SCHEMA
    profile_id: str = Field(min_length=1, max_length=160)
    revision: Literal[1]
    content_hash: str = Field(pattern=SHA256)
    platform: Literal["niushop"]
    source_kind: Literal["synthetic", "historical_redacted"]
    generic_capability_ref: InvestigationExactRef
    enabled: Literal[False]
    source_access_authorized: Literal[False]
    installation_ref: None
    instance_overlay_ref: None
    menu_semantics: list[NiushopMenuSemantic] = Field(min_length=1, max_length=30)
    database_policy: NiushopReadOnlyDatabasePolicy
    database_domains: list[NiushopDatabaseDomain] = Field(min_length=1, max_length=30)
    object_mappings: list[NiushopObjectMapping] = Field(min_length=1, max_length=30)
    known_risks: list[str] = Field(min_length=1, max_length=20)
    non_claims: list[str] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if self.schema_version != PROFILE_SCHEMA:
            raise ValueError("unsupported Niushop Profile schema")
        if self.generic_capability_ref.resource_type != "AdapterCapabilityMatrixRevision":
            raise ValueError("genericCapabilityRef must reference AdapterCapabilityMatrixRevision")
        if len({item.semantic_id for item in self.menu_semantics}) != len(self.menu_semantics):
            raise ValueError("menu semantic IDs must be unique")
        if len({item.domain_id for item in self.database_domains}) != len(self.database_domains):
            raise ValueError("database domain IDs must be unique")
        if len({item.mapping_id for item in self.object_mappings}) != len(self.object_mappings):
            raise ValueError("object mapping IDs must be unique")
        families = {family for item in self.menu_semantics for family in item.fact_families}
        if not NIUSHOP_SEMANTIC_FAMILIES <= families:
            raise ValueError("required Niushop semantic families are incomplete")
        types = {value for item in self.object_mappings for value in item.canonical_types}
        if not NIUSHOP_CANONICAL_TYPES <= types:
            raise ValueError("required Niushop canonical types are incomplete")
        domains = {item.domain_id for item in self.database_domains}
        if any(not set(item.source_domains) <= domains for item in self.object_mappings):
            raise ValueError("object mapping references an unknown database domain")
        return self

    def calculated_hash(self) -> str:
        value = self.model_dump(by_alias=True, mode="json")
        value.pop("contentHash")
        return _canonical_hash(value)


class NiushopProfileAcceptanceReceipt(AipContractModel):
    schema_version: str = ACCEPTANCE_SCHEMA
    profile_ref: InvestigationExactRef
    menu_semantic_count: int = Field(ge=1)
    database_domain_count: int = Field(ge=1)
    object_mapping_count: int = Field(ge=1)
    status: Literal["passed"]
    non_claims: list[str] = Field(min_length=1)


def evaluate_niushop_profile(profile: NiushopProfile) -> NiushopProfileAcceptanceReceipt:
    if profile.calculated_hash() != profile.content_hash:
        raise ValueError("profile content hash drifted")
    return NiushopProfileAcceptanceReceipt(
        profileRef={
            "resourceType": "NiushopAdapterProfileRevision",
            "resourceId": profile.profile_id,
            "revision": profile.revision,
            "contentHash": profile.content_hash,
        },
        menuSemanticCount=len(profile.menu_semantics),
        databaseDomainCount=len(profile.database_domains),
        objectMappingCount=len(profile.object_mappings),
        status="passed",
        nonClaims=[
            "NO_SOURCE_READ",
            "NO_PHYSICAL_TABLE_EXISTENCE_CLAIM",
            "NO_OBJECT_HYDRATION",
            "NO_ADAPTER_INSTALLATION",
            "NO_EXTERNAL_EFFECT",
        ],
    )

"""Strict D0 semantic authority descriptors for ecommerce data slices."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext


DATA_AUTHORITY_SCHEMA_VERSION = "aos.ecommerce.data-authority/v1"


class AuthorityPersistenceState(StrEnum):
    EXISTING_ORIGINAL = "existing_original"
    CONTRACT_ONLY = "contract_only"


class AuthorityPiiClass(StrEnum):
    NONE = "none"


class EcommerceAuthorityField(AipContractModel):
    name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,79}$")
    value_type: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")
    required: bool
    pii_class: Literal[AuthorityPiiClass.NONE] = AuthorityPiiClass.NONE


def _canonical_hash(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def authority_content_hash(
    *,
    authority_id: str,
    resource_type: str,
    semantic_revision: int,
    persistence_state: AuthorityPersistenceState,
    fields: list[EcommerceAuthorityField],
) -> str:
    return _canonical_hash(
        {
            "schemaVersion": DATA_AUTHORITY_SCHEMA_VERSION,
            "authorityId": authority_id,
            "resourceType": resource_type,
            "semanticRevision": semantic_revision,
            "persistenceState": persistence_state.value,
            "fields": [field.model_dump(mode="json", by_alias=True) for field in fields],
        }
    )


def authority_scope_binding_hash(
    *, tenant: TenantContext, content_hash: str
) -> str:
    return _canonical_hash(
        {
            "orgId": tenant.org_id,
            "projectId": tenant.project_id,
            "contentHash": content_hash,
        }
    )


class EcommerceDataAuthorityDescriptor(AipContractModel):
    schema_version: Literal[DATA_AUTHORITY_SCHEMA_VERSION] = (
        DATA_AUTHORITY_SCHEMA_VERSION
    )
    tenant: TenantContext
    authority_id: str = Field(pattern=r"^[a-z][a-z0-9.-]{2,119}$")
    resource_type: str = Field(pattern=r"^[A-Z][A-Za-z0-9]{1,119}$")
    semantic_revision: int = Field(ge=1)
    persistence_state: AuthorityPersistenceState
    receipt_id: str = Field(min_length=1, max_length=200)
    fields: list[EcommerceAuthorityField] = Field(min_length=1, max_length=40)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    scope_binding_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _exact_hashes(self) -> EcommerceDataAuthorityDescriptor:
        expected_content = authority_content_hash(
            authority_id=self.authority_id,
            resource_type=self.resource_type,
            semantic_revision=self.semantic_revision,
            persistence_state=self.persistence_state,
            fields=self.fields,
        )
        if self.content_hash != expected_content:
            raise ValueError("data authority contentHash does not match semantics")
        expected_scope = authority_scope_binding_hash(
            tenant=self.tenant,
            content_hash=self.content_hash,
        )
        if self.scope_binding_hash != expected_scope:
            raise ValueError("data authority scopeBindingHash does not match tenant")
        if len({field.name for field in self.fields}) != len(self.fields):
            raise ValueError("data authority field names must be unique")
        return self


__all__ = [
    "DATA_AUTHORITY_SCHEMA_VERSION",
    "AuthorityPersistenceState",
    "AuthorityPiiClass",
    "EcommerceAuthorityField",
    "EcommerceDataAuthorityDescriptor",
    "authority_content_hash",
    "authority_scope_binding_hash",
]

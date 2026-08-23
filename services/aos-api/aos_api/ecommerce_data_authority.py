"""D0 semantic authority registry; no database or provider access."""

from __future__ import annotations

from dataclasses import dataclass

from aos_api.aip_contracts import TenantContext
from aos_api.ecommerce_data_authority_contracts import (
    AuthorityPersistenceState,
    EcommerceAuthorityField,
    EcommerceDataAuthorityDescriptor,
    authority_content_hash,
    authority_scope_binding_hash,
)


_RECEIPT_ID = "d0-inventory-aftersales-authority-code-20260824"


@dataclass(frozen=True)
class _SemanticAuthority:
    authority_id: str
    resource_type: str
    semantic_revision: int
    persistence_state: AuthorityPersistenceState
    fields: tuple[EcommerceAuthorityField, ...]


_AUTHORITIES = (
    _SemanticAuthority(
        authority_id="inventory.product-sku",
        resource_type="ProductSku",
        semantic_revision=1,
        persistence_state=AuthorityPersistenceState.EXISTING_ORIGINAL,
        fields=(
            EcommerceAuthorityField(
                name="stock", value_type="integer_string", required=False
            ),
            EcommerceAuthorityField(
                name="stockAlarm", value_type="integer_string", required=False
            ),
            EcommerceAuthorityField(
                name="stock_health", value_type="enum", required=False
            ),
            EcommerceAuthorityField(
                name="updatedAt", value_type="datetime", required=True
            ),
        ),
    ),
    _SemanticAuthority(
        authority_id="aftersale.event",
        resource_type="AfterSalesEvent",
        semantic_revision=1,
        persistence_state=AuthorityPersistenceState.CONTRACT_ONLY,
        fields=(
            EcommerceAuthorityField(name="eventId", value_type="string", required=True),
            EcommerceAuthorityField(name="orderRef", value_type="exact_ref", required=True),
            EcommerceAuthorityField(
                name="orderLineRef", value_type="exact_ref", required=False
            ),
            EcommerceAuthorityField(name="eventType", value_type="enum", required=True),
            EcommerceAuthorityField(name="status", value_type="enum", required=True),
            EcommerceAuthorityField(
                name="occurredAt", value_type="datetime", required=True
            ),
            EcommerceAuthorityField(
                name="sourceRevision", value_type="integer", required=True
            ),
            EcommerceAuthorityField(
                name="sourceHash", value_type="sha256", required=True
            ),
        ),
    ),
)


class EcommerceDataAuthority:
    """Build tenant-bound descriptors from immutable semantic definitions."""

    def read_all(
        self, *, org_id: str, project_id: str
    ) -> list[EcommerceDataAuthorityDescriptor]:
        tenant = TenantContext(org_id=org_id, project_id=project_id)
        descriptors = []
        for authority in _AUTHORITIES:
            fields = list(authority.fields)
            content_hash = authority_content_hash(
                authority_id=authority.authority_id,
                resource_type=authority.resource_type,
                semantic_revision=authority.semantic_revision,
                persistence_state=authority.persistence_state,
                fields=fields,
            )
            descriptors.append(
                EcommerceDataAuthorityDescriptor(
                    tenant=tenant,
                    authority_id=authority.authority_id,
                    resource_type=authority.resource_type,
                    semantic_revision=authority.semantic_revision,
                    persistence_state=authority.persistence_state,
                    receipt_id=_RECEIPT_ID,
                    fields=fields,
                    content_hash=content_hash,
                    scope_binding_hash=authority_scope_binding_hash(
                        tenant=tenant,
                        content_hash=content_hash,
                    ),
                )
            )
        return descriptors


__all__ = ["EcommerceDataAuthority"]

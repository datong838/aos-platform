"""D0 exact Inventory and aftersales semantic authority tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aos_api.ecommerce_data_authority import EcommerceDataAuthority
from aos_api.ecommerce_data_authority_contracts import (
    EcommerceDataAuthorityDescriptor,
)
from aos_api.ecom_core_models import (
    DERIVED_PROPERTIES,
    OPTIONAL_PROPERTIES,
    REQUIRED_PROPERTIES,
)


def test_d0_descriptors_freeze_exact_semantics_without_business_payload() -> None:
    service = EcommerceDataAuthority()
    descriptors = service.read_all(org_id="org-org", project_id="dev-project")

    assert [item.authority_id for item in descriptors] == [
        "inventory.product-sku",
        "aftersale.event",
    ]
    inventory, aftersales = descriptors
    assert inventory.resource_type == "ProductSku"
    assert inventory.semantic_revision == 1
    assert {field.name for field in inventory.fields} == {
        "stock",
        "stockAlarm",
        "stock_health",
        "updatedAt",
    }
    assert {field.name for field in inventory.fields}.issubset(
        REQUIRED_PROPERTIES["ProductSku"]
        | OPTIONAL_PROPERTIES["ProductSku"]
        | DERIVED_PROPERTIES["ProductSku"]
    )
    assert aftersales.semantic_revision == 2
    assert aftersales.persistence_state == "existing_original"
    assert aftersales.receipt_id == "d0-aftersale-canonical-reader-code-20260824"
    assert all(
        forbidden not in field.name.lower()
        for field in aftersales.fields
        for forbidden in ("phone", "address", "name", "remark", "evidence")
    )
    assert inventory.content_hash.startswith("sha256:")
    assert inventory.scope_binding_hash.startswith("sha256:")


def test_d0_semantic_hash_is_stable_but_scope_binding_is_tenant_specific() -> None:
    service = EcommerceDataAuthority()
    positive = service.read_all(org_id="org-org", project_id="dev-project")
    canary = service.read_all(org_id="dev-org", project_id="dev-project")

    assert [item.content_hash for item in positive] == [
        item.content_hash for item in canary
    ]
    assert [item.scope_binding_hash for item in positive] != [
        item.scope_binding_hash for item in canary
    ]
    assert all(item.tenant.org_id == "org-org" for item in positive)
    assert all(item.tenant.org_id == "dev-org" for item in canary)


def test_d0_descriptor_rejects_hash_tampering_and_unknown_fields() -> None:
    descriptor = EcommerceDataAuthority().read_all(
        org_id="org-org", project_id="dev-project"
    )[0]
    payload = descriptor.model_dump(mode="json", by_alias=True)
    payload["contentHash"] = "sha256:" + "0" * 64
    with pytest.raises(ValidationError):
        EcommerceDataAuthorityDescriptor.model_validate(payload)

    payload = descriptor.model_dump(mode="json", by_alias=True)
    payload["businessPayload"] = {"stock": 1}
    with pytest.raises(ValidationError):
        EcommerceDataAuthorityDescriptor.model_validate(payload)

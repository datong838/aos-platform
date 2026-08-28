"""Deterministic L1 InvestigationProfile/Scope catalog tests."""

from aos_api.ecommerce_business_investigation_profile_catalog import (
    EcommerceInvestigationProfileCatalog,
    STAGE_ORDER,
)
from aos_api.source_readiness_contracts import CANONICAL_QYH_SOURCES


def test_initial_store_catalog_is_exact_deterministic_and_stable() -> None:
    catalog = EcommerceInvestigationProfileCatalog()
    first = catalog.read("initial_store_analysis")
    second = EcommerceInvestigationProfileCatalog().read("initial_store_analysis")
    assert first is not None and second is not None
    profile, scope = first
    assert first == second
    assert profile.content_hash == profile.calculated_content_hash()
    assert scope.content_hash == scope.calculated_content_hash()
    assert profile.exact_ref.resource_type == "InvestigationProfileRevision"
    assert scope.exact_ref.resource_type == "InvestigationScopeRevision"
    assert profile.exact_ref.content_hash == profile.content_hash
    assert scope.exact_ref.content_hash == scope.content_hash


def test_initial_store_profile_preserves_stage_capability_and_fact_contract() -> None:
    resolved = EcommerceInvestigationProfileCatalog().read("initial_store_analysis")
    assert resolved is not None
    profile, scope = resolved
    assert tuple(stage.stage_id for stage in profile.stages) == STAGE_ORDER
    capabilities = [
        capability
        for stage in profile.stages
        for capability in stage.required_capability_ids
    ]
    assert len(capabilities) == len(set(capabilities)) == 11
    assert "build-evidence-pack" in capabilities
    assert "diagnose-metric-change" in capabilities
    assert "compare-alternatives" in capabilities
    object_types = tuple(source.object_type for source in CANONICAL_QYH_SOURCES)
    assert profile.required_fact_profiles == object_types
    assert scope.object_types == object_types
    assert scope.business_entity_selector == "current-business-entity"
    assert scope.coverage == "full-store"
    assert scope.access_mode == profile.safety_mode == "read-only"


def test_catalog_does_not_depend_on_tenant_and_unknown_analysis_fails_closed() -> None:
    catalog = EcommerceInvestigationProfileCatalog()
    assert catalog.read("initial_store_analysis") == catalog.read("initial_store_analysis")
    assert catalog.read("weekly_business_review") is None
    assert catalog.read("") is None

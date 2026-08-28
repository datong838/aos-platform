"""BI-W10 exact Case selection and creation guard tests."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime

import pytest

from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_business_investigation_application import (
    CreateBusinessInvestigationCaseRequest,
    EcommerceBusinessInvestigationApplication,
)
from aos_api.ecommerce_business_investigation_case_selection import (
    BusinessInvestigationCaseSelectionBlocked,
    BusinessInvestigationCaseSelectionConflict,
    BusinessInvestigationCaseSelectionResolver,
    CatalogCanonicalProfileSelectionSource,
    CanonicalProfileSelection,
    CanonicalShopSelection,
    PostgresCanonicalShopSelectionSource,
)
from aos_api.ecommerce_business_investigation_aip_composition import (
    AipProductionCompositionObservation,
)
from aos_api.aip_contracts import TenantContext
from aos_api.source_readiness import SourceReadinessService
from aos_api.tenant_scope import TenantScope
from test_source_readiness_service import Facts, _snapshot


SCOPE = TenantScope("org-org", "dev-project")
HASH_A = "sha256:" + "a" * 64


def ref(kind: str, identity: str, fill: str = "a") -> InvestigationExactRef:
    return InvestigationExactRef(
        resourceType=kind,
        resourceId=identity,
        revision=1,
        contentHash="sha256:" + fill * 64,
    )


SHOP = CanonicalShopSelection(
    ref("ChannelRevision", "niushop:1"),
    ref("BusinessEntityRevision", "niushop:1:1", "b"),
    ref("BusinessEntityChannelBindingRevision", "niushop:1:1", "c"),
)
PROFILE = CanonicalProfileSelection(
    ref("InvestigationProfileRevision", "initial-store", "d"),
    ref("InvestigationScopeRevision", "whole-store", "e"),
    run_creatable=False,
    case_blockers=(),
    run_blockers=("AIP_PRODUCTION_COMPOSITION_NOT_RESOLVED",),
)


class ShopSource:
    def __init__(self, value=SHOP):
        self.value = value

    def read(self, scope):
        assert scope == SCOPE
        return self.value


class ProfileSource:
    def __init__(self, value=PROFILE):
        self.value = value

    def read(self, scope, analysis_type):
        assert scope == SCOPE and analysis_type == "initial_store_analysis"
        return self.value


class CompositionSource:
    def __init__(self, blockers=("AIP_INVESTIGATION_STAGE_TEMPLATE_MISSING",)):
        self.blockers = blockers

    def read(self, scope, analysis_type, **kwargs):
        assert scope == SCOPE and analysis_type == "initial_store_analysis"
        return AipProductionCompositionObservation(
            tenant=TenantContext(orgId=scope.org_id, projectId=scope.project_id),
            analysisType=analysis_type,
            observedAt=datetime.now(UTC),
            ready=not self.blockers,
            blockers=list(self.blockers),
        )


def resolver(*, shop=SHOP, profile=PROFILE, count_delta=0):
    return BusinessInvestigationCaseSelectionResolver(
        readiness_service=SourceReadinessService(Facts(_snapshot(count_delta=count_delta))),
        shop_source=ShopSource(shop),
        profile_source=ProfileSource(profile),
    )


def request(refs=None):
    refs = refs or (
        SHOP.channel_ref,
        SHOP.business_entity_ref,
        SHOP.entity_channel_binding_ref,
        PROFILE.investigation_profile_ref,
        PROFILE.scope_ref,
    )
    return CreateBusinessInvestigationCaseRequest.model_validate(
        {
            "caseId": "case-qyh-initial",
            "analysisType": "initial_store_analysis",
            "title": "栖月汇首次全店经营分析",
            "purposeCode": "business.investigation.initial",
            "channelRef": refs[0].model_dump(by_alias=True, mode="json"),
            "businessEntityRef": refs[1].model_dump(by_alias=True, mode="json"),
            "entityChannelBindingRef": refs[2].model_dump(by_alias=True, mode="json"),
            "investigationProfileRef": refs[3].model_dump(by_alias=True, mode="json"),
            "scopeRef": refs[4].model_dump(by_alias=True, mode="json"),
        }
    )


def test_ready_selection_returns_five_exact_refs_but_separates_run_readiness() -> None:
    actual = resolver().read(SCOPE, "initial_store_analysis")
    assert actual.case_creatable is True
    assert actual.run_creatable is False
    assert actual.blockers == []
    assert actual.run_blockers == ["AIP_PRODUCTION_COMPOSITION_NOT_RESOLVED"]
    assert actual.business_entity_ref == SHOP.business_entity_ref
    assert actual.investigation_profile_ref == PROFILE.investigation_profile_ref


def test_source_failure_and_missing_profile_fail_closed_without_placeholder_refs() -> None:
    actual = resolver(profile=None, count_delta=1).read(SCOPE, "initial_store_analysis")
    assert actual.case_creatable is False
    assert actual.run_creatable is False
    assert "SOURCE_READINESS_NOT_READY" in actual.blockers
    assert "INVESTIGATION_PROFILE_AUTHORITY_MISSING" in actual.blockers
    assert actual.run_blockers == ["CASE_SELECTION_NOT_CREATABLE"]
    assert actual.investigation_profile_ref is None and actual.scope_ref is None


def test_default_catalog_resolves_l1_refs_without_claiming_runtime_ready() -> None:
    actual = BusinessInvestigationCaseSelectionResolver(
        readiness_service=SourceReadinessService(Facts(_snapshot())),
        shop_source=ShopSource(),
        profile_source=CatalogCanonicalProfileSelectionSource(
            composition_source=CompositionSource()
        ),
    ).read(SCOPE, "initial_store_analysis")
    assert actual.case_creatable is True
    assert actual.run_creatable is False
    assert actual.blockers == []
    assert actual.run_blockers == ["AIP_INVESTIGATION_STAGE_TEMPLATE_MISSING"]
    assert actual.investigation_profile_ref is not None
    assert actual.investigation_profile_ref.resource_id == "ecommerce.initial-store-analysis"
    assert actual.scope_ref is not None
    assert actual.scope_ref.resource_id == (
        "ecommerce.current-business-entity.full-store.readonly"
    )


def test_unknown_analysis_type_keeps_l1_refs_missing() -> None:
    actual = BusinessInvestigationCaseSelectionResolver(
        readiness_service=SourceReadinessService(Facts(_snapshot())),
        shop_source=ShopSource(),
        profile_source=CatalogCanonicalProfileSelectionSource(
            composition_source=CompositionSource()
        ),
    ).read(SCOPE, "weekly_business_review")
    assert actual.case_creatable is False
    assert actual.investigation_profile_ref is None
    assert "INVESTIGATION_PROFILE_AUTHORITY_MISSING" in actual.blockers


def test_exact_ref_drift_is_rejected_before_case_store_access() -> None:
    changed = SHOP.business_entity_ref.model_copy(update={"content_hash": HASH_A})
    submitted = request(
        (
            SHOP.channel_ref,
            changed,
            SHOP.entity_channel_binding_ref,
            PROFILE.investigation_profile_ref,
            PROFILE.scope_ref,
        )
    )

    class NeverStore:
        def create_draft(self, *args, **kwargs):
            raise AssertionError("Case store must not be reached on exact-ref drift")

    application = EcommerceBusinessInvestigationApplication(
        case_store=NeverStore(), case_selection_resolver=resolver()
    )
    with pytest.raises(BusinessInvestigationCaseSelectionConflict, match="canonical"):
        application.create_case(
            SCOPE,
            submitted,
            idempotency_key="case-create",
            actor="owner",
            occurred_at=datetime.now(UTC),
        )


def test_unready_selection_blocks_case_before_store_access() -> None:
    class NeverStore:
        def create_draft(self, *args, **kwargs):
            raise AssertionError("Case store must not be reached while readiness is failed")

    application = EcommerceBusinessInvestigationApplication(
        case_store=NeverStore(), case_selection_resolver=resolver(count_delta=1)
    )
    with pytest.raises(BusinessInvestigationCaseSelectionBlocked) as raised:
        application.create_case(
            SCOPE,
            request(),
            idempotency_key="case-create",
            actor="owner",
            occurred_at=datetime.now(UTC),
        )
    assert "SOURCE_READINESS_NOT_READY" in raised.value.blockers


def test_postgres_shop_selection_is_tenant_bound_and_payload_drift_changes_hash() -> None:
    row = {
        "platform": "niushop",
        "shop_or_marketplace_id": "1",
        "external_id": "1",
        "schema_version": 1,
        "payload_hash": "1" * 64,
        "source_updated_at": datetime(2026, 8, 28, tzinfo=UTC),
    }

    class Cursor:
        def __init__(self, rows):
            self.rows = rows

        def fetchall(self):
            return self.rows

    class Connection:
        def __init__(self, rows):
            self.rows = rows

        def execute(self, sql, params):
            assert "object_type='Shop'" in sql and params == SCOPE.key
            return Cursor(self.rows)

    def source(rows):
        @contextmanager
        def connect(scope):
            assert scope == SCOPE
            yield Connection(rows)

        return PostgresCanonicalShopSelectionSource(connect).read(SCOPE)

    first = source([row])
    second = source([{**row, "payload_hash": "2" * 64}])
    assert first is not None and second is not None
    assert first.business_entity_ref.resource_id == "1"
    assert first.business_entity_ref.content_hash != second.business_entity_ref.content_hash
    assert source([]) is None and source([row, row]) is None

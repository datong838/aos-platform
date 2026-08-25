"""Canonical W1 ecommerce Workshop HTTP contract tests."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.asset_registry.errors import AssetNotFoundError
from aos_api.auth import Principal, require_principal
from aos_api.ecommerce_workshop_contracts import (
    EcommerceWorkshopModuleListResponse,
    EcommerceWorkshopModuleReadinessResponse,
)
from aos_api.ecommerce_workshop_source_readiness import (
    SourceReadinessTenantMismatchError,
)
from aos_api.errors import register_exception_handlers
from aos_api.routers import ecommerce_workshop
from aos_api.source_readiness_contracts import (
    CANONICAL_QYH_SOURCES,
    SourceReadinessEnvelope,
)

NOW = datetime(2026, 8, 14, tzinfo=UTC)


def _module():
    return {
        "moduleId": "ecommerce.operations",
        "displayName": "统一运营驾驶舱",
        "menuLabel": "统一运营驾驶舱",
        "route": "/workshop/operations",
        "slot": "workshop.primary.ecommerce",
        "order": 30,
        "installationRef": {
            "installationId": "11111111-1111-4111-8111-111111111111",
            "revision": 5,
            "compositionId": "22222222-2222-4222-8222-222222222222",
            "lockRevision": 1,
            "lockHash": "sha256:" + "a" * 64,
            "overlayRevision": "overlay-5",
        },
        "moduleRef": {
            "publisher": "aos",
            "bundleId": "solution.ecommerce.operations-base",
            "version": "1.1.0",
            "bundleContentHash": "sha256:" + "b" * 64,
            "moduleArtifactRef": "bundle://catalog/solutions/ecommerce-operations-base/content/workshops/ecommerce.operations.json",
            "moduleArtifactHash": "sha256:" + "c" * 64,
        },
        "readiness": "unknown",
        "blockers": [
            {
                "dependencyType": "aip_feature",
                "dependencyId": "aip.task-runtime",
                "state": "unknown",
                "reasonCode": "AIP_FEATURE_UNVERIFIED",
                "recoverable": True,
                "requiredAction": "等待 canonical reader 回读",
                "ref": None,
            }
        ],
        "permissions": {
            "roles": [],
            "markings": [],
            "dataScopes": ["ecommerce.workshop.read"],
            "actionTypes": [],
        },
        "requiredObjects": ["Order"],
        "requiredCapabilities": ["performance.review"],
        "requiredAipFeatures": ["aip.task-runtime"],
        "viewRefs": [],
        "evalPackRefs": [],
        "productionContractRefs": [],
        "responsibilityTemplateRefs": [],
        "impactCalculatorRefs": [],
        "legacyAssetRefs": [],
        "legacyRoutes": ["/workshop/orders"],
        "minimumRuntimeVersion": "1.7.0",
        "lastReceiptRef": None,
    }


class FakeCatalog:
    def __init__(self):
        self.calls = []

    def list_modules(self, **kwargs):
        self.calls.append(("list", kwargs))
        return EcommerceWorkshopModuleListResponse.model_validate(
            {
                "schemaVersion": "aos.ecommerce-workshop/v1",
                "tenant": {"orgId": kwargs["org_id"], "projectId": kwargs["project_id"]},
                "evaluatedAt": NOW,
                "dataCutoff": None,
                "items": [_module()],
                "count": 1,
            }
        )

    def get_readiness(self, **kwargs):
        self.calls.append(("readiness", kwargs))
        if kwargs["module_id"] == "ecommerce.not-installed":
            raise AssetNotFoundError("Workshop module is not installed")
        return EcommerceWorkshopModuleReadinessResponse.model_validate(
            {
                "schemaVersion": "aos.ecommerce-workshop/v1",
                "tenant": {"orgId": kwargs["org_id"], "projectId": kwargs["project_id"]},
                "evaluatedAt": NOW,
                "dataCutoff": None,
                "item": _module(),
            }
        )


def _source_envelope(*, org_id: str = "org-org") -> SourceReadinessEnvelope:
    blockers = [
        "SOURCE_CONFIG_EXACT_REF_MISSING",
        "FRESHNESS_POLICY_REF_MISSING",
        "QUALITY_POLICY_REF_MISSING",
        "RECONCILIATION_POLICY_REF_MISSING",
        "QUERY_CAPABILITY_REF_MISSING",
    ]
    return SourceReadinessEnvelope.model_validate(
        {
            "tenant": {"orgId": org_id, "projectId": "dev-project"},
            "checkedAt": NOW,
            "cutoffAt": NOW,
            "status": "blocked",
            "sources": [
                {
                    "tenant": {"orgId": org_id, "projectId": "dev-project"},
                    "sourceId": "niushop-qyh",
                    "pipelineId": source.pipeline_id,
                    "objectType": source.object_type,
                    "status": "blocked",
                    "checkedAt": NOW,
                    "reasons": blockers,
                    "blockers": blockers,
                }
                for source in CANONICAL_QYH_SOURCES
            ],
        }
    )


class FakeSourceReadiness:
    def __init__(self, *, mismatch: bool = False) -> None:
        self.mismatch = mismatch
        self.calls: list[tuple[str, str]] = []

    def read(self, *, org_id: str, project_id: str) -> SourceReadinessEnvelope:
        self.calls.append((org_id, project_id))
        if self.mismatch:
            raise SourceReadinessTenantMismatchError("tenant mismatch")
        return _source_envelope()


def _client(
    catalog: FakeCatalog,
    source_readiness: FakeSourceReadiness | None = None,
) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(ecommerce_workshop.router)
    app.dependency_overrides[require_principal] = lambda: Principal(
        subject="user:test",
        org_id="org-org",
        project_id="dev-project",
        roles=["operator"],
        markings=["public"],
    )
    app.dependency_overrides[ecommerce_workshop.get_ecommerce_workshop_catalog] = lambda: catalog
    app.dependency_overrides[
        ecommerce_workshop.get_ecommerce_workshop_source_readiness
    ] = lambda: source_readiness or FakeSourceReadiness()
    return TestClient(app, raise_server_exceptions=False)


def test_routes_use_principal_tenant_and_have_no_scope_injection_surface() -> None:
    catalog = FakeCatalog()
    with _client(catalog) as client:
        response = client.get("/v1/ecommerce-workshop/modules")
        assert response.status_code == 200
        assert response.json()["tenant"] == {
            "orgId": "org-org",
            "projectId": "dev-project",
        }
        injected = client.get(
            "/v1/ecommerce-workshop/modules?orgId=dev-org&projectId=other"
        )
        assert injected.status_code == 400
        assert injected.json()["code"] == "VALIDATION"
        duplicated = client.get(
            "/v1/ecommerce-workshop/modules/ecommerce.operations/readiness?x=1&x=2"
        )
        assert duplicated.status_code == 400
        readiness = client.get(
            "/v1/ecommerce-workshop/modules/ecommerce.operations/readiness"
        )
        assert readiness.status_code == 200

    assert all(call[1]["org_id"] == "org-org" for call in catalog.calls)
    assert all(call[1]["project_id"] == "dev-project" for call in catalog.calls)
    assert all("org_id" not in call[1].get("body", {}) for call in catalog.calls)
    assert [call[0] for call in catalog.calls] == ["list", "readiness"]


def test_not_installed_and_invalid_module_id_fail_explicitly() -> None:
    with _client(FakeCatalog()) as client:
        missing = client.get(
            "/v1/ecommerce-workshop/modules/ecommerce.not-installed/readiness"
        )
        assert missing.status_code == 404
        assert missing.json()["code"] == "NOT_FOUND"
        invalid = client.get(
            "/v1/ecommerce-workshop/modules/other-module/readiness"
        )
        assert invalid.status_code == 400
        assert invalid.json()["code"] == "VALIDATION"


def test_source_readiness_is_installation_gated_and_principal_scoped() -> None:
    catalog = FakeCatalog()
    source_readiness = FakeSourceReadiness()
    with _client(catalog, source_readiness) as client:
        response = client.get("/v1/ecommerce-workshop/source-readiness")
        assert response.status_code == 200
        assert response.json()["status"] == "blocked"
        assert len(response.json()["sources"]) == 12
        injected = client.get(
            "/v1/ecommerce-workshop/source-readiness?orgId=dev-org"
        )
        assert injected.status_code == 400
        assert injected.json()["code"] == "VALIDATION"

    assert source_readiness.calls == [("org-org", "dev-project")]
    assert catalog.calls == [
        (
            "list",
            {
                "org_id": "org-org",
                "project_id": "dev-project",
                "roles": ["operator"],
                "markings": ["public"],
            },
        )
    ]


def test_source_readiness_zero_visible_modules_and_tenant_drift_fail_closed() -> None:
    class EmptyCatalog(FakeCatalog):
        def list_modules(self, **kwargs):
            self.calls.append(("list", kwargs))
            return EcommerceWorkshopModuleListResponse.model_validate(
                {
                    "tenant": {
                        "orgId": kwargs["org_id"],
                        "projectId": kwargs["project_id"],
                    },
                    "evaluatedAt": NOW,
                    "dataCutoff": None,
                    "items": [],
                    "count": 0,
                }
            )

    unread = FakeSourceReadiness()
    with _client(EmptyCatalog(), unread) as client:
        missing = client.get("/v1/ecommerce-workshop/source-readiness")
        assert missing.status_code == 404
        assert missing.json()["code"] == "WORKSHOP_NOT_INSTALLED"
    assert unread.calls == []

    mismatch = FakeSourceReadiness(mismatch=True)
    with _client(FakeCatalog(), mismatch) as client:
        rejected = client.get("/v1/ecommerce-workshop/source-readiness")
        assert rejected.status_code == 500
        assert rejected.json()["code"] == "SOURCE_READINESS_TENANT_MISMATCH"
        assert rejected.json()["message"] == "SourceReadiness dependency failed closed"


def test_openapi_freezes_workshop_reads_and_governed_internal_commands() -> None:
    app = FastAPI()
    app.include_router(ecommerce_workshop.router)
    schema = app.openapi()
    operations = {
        operation["operationId"]: (path, method)
        for path, item in schema["paths"].items()
        for method, operation in item.items()
        if method in {"get", "post", "put", "patch", "delete"}
    }
    assert operations == {
        "ecommerceWorkshopModulesList": (
            "/v1/ecommerce-workshop/modules",
            "get",
        ),
        "ecommerceWorkshopModuleReadinessGet": (
            "/v1/ecommerce-workshop/modules/{module_id}/readiness",
            "get",
        ),
        "ecommerceWorkshopPrepare": (
            "/v1/ecommerce-workshop/modules/{module_id}/commands/prepare",
            "post",
        ),
        "ecommerceWorkshopBuildEvidence": (
            "/v1/ecommerce-workshop/modules/{module_id}/commands/build-evidence",
            "post",
        ),
        "ecommerceWorkshopFreeze": (
            "/v1/ecommerce-workshop/modules/{module_id}/commands/freeze",
            "post",
        ),
        "ecommerceWorkshopSourceReadinessGet": (
            "/v1/ecommerce-workshop/source-readiness",
            "get",
        ),
        "ecommerceWorkshopOperationsViewGet": (
            "/v1/ecommerce-workshop/views/operations",
            "get",
        ),
        "ecommerceWorkshopContentCampaignViewGet": (
            "/v1/ecommerce-workshop/views/content-campaign",
            "get",
        ),
            "ecommerceWorkshopCreatorGrowthViewGet": (
                "/v1/ecommerce-workshop/views/creator-growth",
                "get",
            ),
            "ecommerceWorkshopCreatorDiscoveryProfileCreate": (
                "/v1/ecommerce-workshop/creator-growth/discovery-profiles",
                "post",
            ),
            "ecommerceWorkshopCreatorArtifactNormalize": (
                "/v1/ecommerce-workshop/creator-growth/normalize",
                "post",
            ),
            "ecommerceWorkshopCreatorMatchObservationCreate": (
                "/v1/ecommerce-workshop/creator-growth/match-observations",
                "post",
            ),
            "ecommerceWorkshopCreatorMatchDecisionCreate": (
                "/v1/ecommerce-workshop/creator-growth/match-decisions",
                "post",
            ),
            "ecommerceWorkshopCreatorBatchPrepare": (
                "/v1/ecommerce-workshop/creator-growth/batches/prepare",
                "post",
            ),
            "ecommerceWorkshopCreatorBatchFreeze": (
                "/v1/ecommerce-workshop/creator-growth/batches/{batch_id}/freeze",
                "post",
            ),
            "ecommerceWorkshopCreatorContributionViewGet": (
                "/v1/ecommerce-workshop/views/creator-growth/contributions",
                "get",
            ),
            "ecommerceWorkshopCreatorBatchStart": (
                "/v1/ecommerce-workshop/creator-growth/batches/{batch_id}/start",
                "post",
            ),
            "ecommerceWorkshopCreatorLifecycleViewGet": (
                "/v1/ecommerce-workshop/views/creator-growth/lifecycle",
                "get",
            ),
        "ecommerceWorkshopMediaStudioViewGet": (
            "/v1/ecommerce-workshop/views/media-studio",
            "get",
        ),
        "ecommerceWorkshopAnalystViewGet": (
            "/v1/ecommerce-workshop/views/analyst",
            "get",
        ),
        "ecommerceWorkshopPriceGovernanceViewGet": (
            "/v1/ecommerce-workshop/views/price-governance",
            "get",
        ),
        "ecommerceWorkshopPriceResearchProfileCreate": (
            "/v1/ecommerce-workshop/price-governance/research-profiles",
            "post",
        ),
        "ecommerceWorkshopPriceObservationNormalize": (
            "/v1/ecommerce-workshop/price-governance/observations/normalize",
            "post",
        ),
        "ecommerceWorkshopPriceMatchObservationCreate": (
            "/v1/ecommerce-workshop/price-governance/match-observations",
            "post",
        ),
        "ecommerceWorkshopPriceMatchDecisionCreate": (
            "/v1/ecommerce-workshop/price-governance/match-decisions",
            "post",
        ),
        "ecommerceWorkshopPriceMonitoringPolicyCreate": (
            "/v1/ecommerce-workshop/price-governance/monitoring-policies",
            "post",
        ),
        "ecommerceWorkshopPriceResearchBatchPrepare": (
            "/v1/ecommerce-workshop/price-governance/batches/prepare",
            "post",
        ),
        "ecommerceWorkshopPriceResearchBatchFreeze": (
            "/v1/ecommerce-workshop/price-governance/batches/{batch_id}/freeze",
            "post",
        ),
        "ecommerceWorkshopPriceResearchContributionViewGet": (
            "/v1/ecommerce-workshop/views/price-governance/contributions",
            "get",
        ),
        "ecommerceWorkshopPriceCaseCreate": (
            "/v1/ecommerce-workshop/price-governance/cases",
            "post",
        ),
        "ecommerceWorkshopPriceDispositionContractCreate": (
            "/v1/ecommerce-workshop/price-governance/disposition-contracts",
            "post",
        ),
        "ecommerceWorkshopPriceDispositionPrepare": (
            "/v1/ecommerce-workshop/price-governance/dispositions/prepare",
            "post",
        ),
        "ecommerceWorkshopPriceDispositionFreeze": (
            "/v1/ecommerce-workshop/price-governance/dispositions/{disposition_id}/freeze",
            "post",
        ),
        "ecommerceWorkshopPriceDispositionObservationRecord": (
            "/v1/ecommerce-workshop/price-governance/disposition-observations",
            "post",
        ),
        "ecommerceWorkshopPriceDispositionContributionViewGet": (
            "/v1/ecommerce-workshop/views/price-governance/dispositions",
            "get",
        ),
        "ecommerceWorkshopCustomerViewGet": (
            "/v1/ecommerce-workshop/views/customer",
            "get",
        ),
        "ecommerceWorkshopCustomerConsentPolicyCreate": (
            "/v1/ecommerce-workshop/customer/consent-policies",
            "post",
        ),
        "ecommerceWorkshopCustomerSegmentCreate": (
            "/v1/ecommerce-workshop/customer/segments",
            "post",
        ),
        "ecommerceWorkshopCustomerJourneyCreate": (
            "/v1/ecommerce-workshop/customer/journeys",
            "post",
        ),
        "ecommerceWorkshopCustomerDialogueCreate": (
            "/v1/ecommerce-workshop/customer/dialogues",
            "post",
        ),
        "ecommerceWorkshopCustomerDialogueBatchPrepare": (
            "/v1/ecommerce-workshop/customer/dialogue-batches/prepare",
            "post",
        ),
        "ecommerceWorkshopCustomerDialogueBatchFreeze": (
            "/v1/ecommerce-workshop/customer/dialogue-batches/{batch_id}/freeze",
            "post",
        ),
        "ecommerceWorkshopCustomerLifecycleContributionViewGet": (
            "/v1/ecommerce-workshop/views/customer/contributions",
            "get",
        ),
        "ecommerceWorkshopCustomerFrequencyPolicyCreate": (
            "/v1/ecommerce-workshop/customer/frequency-policies",
            "post",
        ),
        "ecommerceWorkshopCustomerConsentWithdrawalRecord": (
            "/v1/ecommerce-workshop/customer/consent-withdrawals",
            "post",
        ),
        "ecommerceWorkshopCustomerDialogueBatchStartGovernance": (
            "/v1/ecommerce-workshop/customer/dialogue-batches/{batch_id}/start-governance",
            "post",
        ),
        "ecommerceWorkshopCustomerDispatchObservationRecord": (
            "/v1/ecommerce-workshop/customer/dispatch-observations",
            "post",
        ),
        "ecommerceWorkshopCustomerContactContributionViewGet": (
            "/v1/ecommerce-workshop/views/customer/contact-contributions",
            "get",
        ),
        "ecommerceWorkshopSharedContextGet": (
            "/v1/ecommerce-workshop/contexts/{context_id}",
            "get",
        ),
        "ecommerceWorkshopOperationCommandReadinessGet": (
            "/v1/ecommerce-workshop/commands/operations/readiness",
            "get",
        ),
        "ecommerceWorkshopOperationCommandObservationGet": (
            "/v1/ecommerce-workshop/commands/operations/observations/{proposal_id}/leases/{lease_id}",
            "get",
        ),
        "ecommerceWorkshopOperationClassifyPost": (
            "/v1/ecommerce-workshop/commands/operations/classify",
            "post",
        ),
        "ecommerceWorkshopOperationCreateCasePost": (
            "/v1/ecommerce-workshop/commands/operations/create-case",
            "post",
        ),
        "ecommerceWorkshopOperationChangeMembershipPost": (
            "/v1/ecommerce-workshop/commands/operations/change-membership",
            "post",
        ),
        "ecommerceWorkshopOperationManageSlaPost": (
            "/v1/ecommerce-workshop/commands/operations/manage-sla",
            "post",
        ),
        "ecommerceWorkshopOperationAutomationKillPost": (
            "/v1/ecommerce-workshop/commands/operations/automation-kill",
            "post",
        ),
        "ecommerceWorkshopTaskCockpitCoreGet": (
            "/v1/ecommerce-workshop/views/task-cockpit",
            "get",
        ),
        "ecommerceWorkshopTaskCockpitRunStepsList": (
            "/v1/ecommerce-workshop/views/task-cockpit/runs/{run_id}/steps",
            "get",
        ),
        "ecommerceWorkshopTaskCockpitRunCheckpointsList": (
            "/v1/ecommerce-workshop/views/task-cockpit/runs/{run_id}/checkpoints",
            "get",
        ),
        "ecommerceWorkshopTaskCockpitRunProductionContextGet": (
            "/v1/ecommerce-workshop/views/task-cockpit/runs/{run_id}/production-context",
            "get",
        ),
        "ecommerceWorkshopTaskCockpitRunSkillContributionsGet": (
            "/v1/ecommerce-workshop/views/task-cockpit/runs/{run_id}/skill-contributions",
            "get",
        ),
        "ecommerceWorkshopTaskCockpitRunResponsibilityHandoffsGet": (
            "/v1/ecommerce-workshop/views/task-cockpit/runs/{run_id}/responsibility-handoffs",
            "get",
        ),
        "ecommerceWorkshopTaskCockpitRunApprovalReviewIssuesGet": (
            "/v1/ecommerce-workshop/views/task-cockpit/runs/{run_id}/approval-review-issues",
            "get",
        ),
        "ecommerceWorkshopTaskCockpitRunActionReceiptsGet": (
            "/v1/ecommerce-workshop/views/task-cockpit/runs/{run_id}/action-receipts",
            "get",
        ),
        "ecommerceWorkshopTaskCockpitRunHandoffCompile": (
            "/v1/ecommerce-workshop/views/task-cockpit/runs/{run_id}/handoffs/compile",
            "post",
        ),
    }
    assert all(method in {"get", "post"} for _, method in operations.values())
    assert not any("refund" in path for path, _ in operations.values())

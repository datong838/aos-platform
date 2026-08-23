from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.aip_marketplace_catalog import AipMarketplaceCatalog
from aos_api.auth import Principal, require_principal
from aos_api.routers.phase3_aip_agents import get_marketplace_catalog, router


def _principal(org_id: str = "org-org") -> Principal:
    return Principal(subject="pytest", org_id=org_id, project_id="dev-project")


class _Installer:
    def catalog(self, principal: Principal):
        del principal
        items = [
            SimpleNamespace(
                template=SimpleNamespace(
                    template_id=f"ecommerce.agent.role-{index}",
                    display_name=f"数字同事 {index}",
                ),
                instance=object() if index <= 2 else None,
                runtime_readiness="runnable" if index == 1 else "blocked",
                blockers=[] if index == 1 else ["capability_bindings_unavailable"],
            )
            for index in range(1, 7)
        ]
        return SimpleNamespace(
            items=items,
            stats=SimpleNamespace(installed_count=2, runnable_count=1),
        )


def test_marketplace_is_a_read_only_projection_of_the_versioned_bundle() -> None:
    catalog = AipMarketplaceCatalog(installer=_Installer()).list(_principal())

    assert catalog.tenant.org_id == "org-org"
    assert catalog.tenant.project_id == "dev-project"
    assert catalog.count == 1
    package = catalog.items[0]
    assert package.package_id == "solution.ecommerce.growth"
    assert package.version == "1.3.0"
    assert package.source_ref.resource_type == "SolutionPack"
    assert package.source_ref.resource_id == package.package_id
    assert package.source_ref.revision == package.version
    assert package.source_ref.authority == "asset-registry"
    assert package.agent_count == 6
    assert package.skill_count == 37
    assert package.capability_count == 10
    assert package.installed_count == 2
    assert package.runnable_count == 1
    assert package.discoverable is True
    assert package.install_authorized is False
    assert len(package.content_hash) == 64
    assert package.agents[1].repair_href == "/aip/agent-registry"
    assert package.agents[1].repair_label == "检查目录与绑定"


def test_marketplace_content_address_is_deterministic_and_tenant_scoped() -> None:
    service = AipMarketplaceCatalog(installer=_Installer())

    first = service.list(_principal())
    second = service.list(_principal())
    canary = service.list(_principal("dev-org"))

    assert first.items[0].content_hash == second.items[0].content_hash
    assert canary.tenant.org_id == "dev-org"
    assert canary.tenant.project_id == "dev-project"


def test_marketplace_http_contract_uses_camel_case_and_never_authorizes_install() -> None:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_principal] = _principal
    app.dependency_overrides[get_marketplace_catalog] = lambda: AipMarketplaceCatalog(installer=_Installer())

    with TestClient(app) as client:
        response = client.get("/v1/aip/marketplace/catalog")

    assert response.status_code == 200
    body = response.json()
    assert body["tenant"] == {"orgId": "org-org", "projectId": "dev-project"}
    assert body["items"][0]["packageId"] == "solution.ecommerce.growth"
    assert body["items"][0]["installAuthorized"] is False
    assert body["items"][0]["agents"][1]["repairHref"] == "/aip/agent-registry"

from __future__ import annotations

from aos_api.aip_solution_pack_publisher import AipSolutionPackPublisher
from aos_api.db import connect
from aos_api.routers.phase3_aip_agents import get_ecommerce_agent_installer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
BUNDLE = REPO_ROOT / "bundles/solutions/ecommerce-growth"


def _headers(org_id: str, *, key: str | None = None) -> dict[str, str]:
    headers = {
        "Authorization": "Bearer dev",
        "X-Org-Id": org_id,
        "X-Project-Id": "dev-project",
    }
    if key:
        headers["Idempotency-Key"] = key
    return headers


def _ensure_tenants_and_clean() -> None:
    with connect() as conn:
        for org_id, name in (("org-org", "栖月汇商贸有限公司"), ("dev-org", "测试组织")):
            conn.execute("INSERT INTO twa_org(id,name) VALUES (%s,%s) ON CONFLICT (id) DO NOTHING", (org_id, name))
            conn.execute(
                "INSERT INTO twa_workspace(org_id,project_id,name) VALUES (%s,'dev-project','默认工作区') ON CONFLICT (org_id,project_id) DO NOTHING",
                (org_id,),
            )
        ids = tuple(f"{item}.default" for item in (
            "ecommerce.data_advisor", "ecommerce.content_officer", "ecommerce.shopping_advisor",
            "ecommerce.customer_service", "ecommerce.private_domain_manager", "ecommerce.campaign_planner",
        ))
        conn.execute("DELETE FROM aip_agent_registry_receipt WHERE org_id IN ('org-org','dev-org') AND result_ref->>'resourceId'=ANY(%s)", (list(ids),))
        conn.execute("DELETE FROM aip_agent_instance WHERE org_id IN ('org-org','dev-org') AND instance_id=ANY(%s)", (list(ids),))
        conn.commit()


def test_runtime_readiness_contract_and_tenant_echo(client):
    class FakeInstaller:
        def runtime_readiness(self, principal):
            tenant = {"orgId": principal.org_id, "projectId": principal.project_id}
            return {
                "tenant": tenant,
                "catalog": {
                    "tenant": tenant,
                    "items": [],
                    "stats": {
                        "definitionCount": 6,
                        "installedCount": 0,
                        "runnableCount": 0,
                        "skillDefinitionCount": 37,
                        "capabilityDefinitionCount": 10,
                    },
                },
                "capabilityBindings": [],
                "skillBindings": [],
                "bindingStats": {
                    "capabilityBindingCount": 0,
                    "skillBindingCount": 0,
                    "activeCapabilityBindingCount": 0,
                    "activeSkillBindingCount": 0,
                },
                "evaluatedAt": "2026-08-15T05:30:00Z",
            }

    client.app.dependency_overrides[get_ecommerce_agent_installer] = FakeInstaller
    try:
        response = client.get(
            "/v1/aip/agent-registry/runtime-readiness",
            headers=_headers("org-org"),
        )
    finally:
        client.app.dependency_overrides.pop(get_ecommerce_agent_installer, None)
    assert response.status_code == 200
    assert response.json()["tenant"] == {
        "orgId": "org-org",
        "projectId": "dev-project",
    }
    assert response.json()["catalog"]["stats"]["runnableCount"] == 0


def test_canonical_catalog_install_replay_and_tenant_canary(client):
    _ensure_tenants_and_clean()
    AipSolutionPackPublisher().publish(BUNDLE, actor="pytest-a6f")

    before = client.get("/v1/aip/agent-registry", headers=_headers("org-org"))
    assert before.status_code == 200
    assert before.json()["stats"] == {
        "definitionCount": 6,
        "installedCount": 0,
        "runnableCount": 0,
        "skillDefinitionCount": 37,
        "capabilityDefinitionCount": 10,
    }

    installed = client.post(
        "/v1/aip/agents/install-ecommerce",
        headers=_headers("org-org", key="pytest-a6f-install"),
    )
    assert installed.status_code == 201
    body = installed.json()
    assert body["status"] == "installed"
    assert (body["createdCount"], body["existingCount"], body["runnableCount"]) == (6, 0, 0)
    assert {item["instance"]["status"] for item in body["items"]} == {"provisioning"}

    replay = client.post(
        "/v1/aip/agents/install-ecommerce",
        headers=_headers("org-org", key="pytest-a6f-install"),
    )
    assert replay.status_code == 201
    assert (replay.json()["createdCount"], replay.json()["existingCount"]) == (0, 6)

    instances = client.get("/v1/aip/agents", headers=_headers("org-org"))
    assert instances.status_code == 200 and instances.json()["count"] == 6
    assert {item["tenant"]["orgId"] for item in instances.json()["items"]} == {"org-org"}

    canary = client.get("/v1/aip/agents", headers=_headers("dev-org"))
    assert canary.status_code == 200 and canary.json()["count"] == 0
    caps = client.get("/v1/aip/capability-catalog", headers=_headers("org-org"))
    assert caps.status_code == 200
    assert (caps.json()["count"], caps.json()["availableCount"]) == (10, 0)

    readiness = client.get(
        "/v1/aip/agent-registry/runtime-readiness",
        headers=_headers("org-org"),
    )
    assert readiness.status_code == 200
    readiness_body = readiness.json()
    assert readiness_body["tenant"] == {
        "orgId": "org-org",
        "projectId": "dev-project",
    }
    assert readiness_body["catalog"]["stats"] == {
        "definitionCount": 6,
        "installedCount": 6,
        "runnableCount": 0,
        "skillDefinitionCount": 37,
        "capabilityDefinitionCount": 10,
    }
    assert readiness_body["bindingStats"] == {
        "capabilityBindingCount": 0,
        "skillBindingCount": 0,
        "activeCapabilityBindingCount": 0,
        "activeSkillBindingCount": 0,
    }
    assert readiness_body["capabilityBindings"] == []
    assert readiness_body["skillBindings"] == []

    canary_readiness = client.get(
        "/v1/aip/agent-registry/runtime-readiness",
        headers=_headers("dev-org"),
    )
    assert canary_readiness.status_code == 200
    assert canary_readiness.json()["tenant"]["orgId"] == "dev-org"
    assert canary_readiness.json()["catalog"]["stats"]["installedCount"] == 0

    with connect() as conn:
        counts = {
            table: conn.execute(
                f"SELECT count(*) AS n FROM {table} WHERE org_id='org-org' AND project_id='dev-project'"
            ).fetchone()["n"]
            for table in ("aip_skill_binding", "aip_capability_binding", "aip_agent_run")
        }
    assert counts == {"aip_skill_binding": 0, "aip_capability_binding": 0, "aip_agent_run": 0}

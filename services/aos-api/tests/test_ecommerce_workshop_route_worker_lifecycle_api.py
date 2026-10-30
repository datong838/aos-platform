from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from aos_api.aip_route_worker_customer_lifecycle import (
    RouteWorkerConfigurationCheck,
    RouteWorkerConfigurationPreview,
    RouteWorkerConfigurationSideEffects,
    RouteWorkerCustomerReceipt,
    RouteWorkerCustomerStatus,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import register_exception_handlers
from aos_api.routers import ecommerce_workshop
from fastapi import FastAPI
from fastapi.testclient import TestClient


class Catalog:
    def get_readiness(self, **kwargs):
        assert kwargs["org_id"] == "org-org"
        assert kwargs["project_id"] == "dev-project"
        return SimpleNamespace(
            item=SimpleNamespace(
                installation_ref=SimpleNamespace(
                    installation_id="00000000-0000-0000-0000-000000000401"
                )
            )
        )


class Service:
    def __init__(self):
        self.calls = []

    def read_status(self):
        return RouteWorkerCustomerStatus(
            schemaVersion="aos.route-worker-customer-status/v1",
            state="configuration_ready",
            title="后台处理配置已就绪",
            summary="配置已经就绪，但运行开关仍保持关闭。",
            canProcessBusinessTasks=False,
            checkedAt=datetime(2026, 10, 30, 21, 30, tzinfo=UTC),
        )

    def _result(self, action, **kwargs):
        self.calls.append((action, kwargs))
        state, title = {
            "enable": ("configuration_ready", "后台处理配置已就绪"),
            "disable": ("disabled", "后台处理已停用"),
            "restore": ("configuration_ready", "后台处理配置已恢复"),
        }[action]
        return RouteWorkerCustomerReceipt(
            schemaVersion="aos.route-worker-customer-receipt/v1",
            receiptId="00000000-0000-0000-0000-000000000402",
            action=action,
            state=state,
            title=title,
            summary="业务操作已记录；运行开关仍保持关闭。",
            canProcessBusinessTasks=False,
            completedAt=datetime(2026, 10, 30, 21, 31, tzinfo=UTC),
        )

    def enable(self, **kwargs):
        return self._result("enable", **kwargs)

    def disable(self, **kwargs):
        return self._result("disable", **kwargs)

    def restore(self, **kwargs):
        return self._result("restore", **kwargs)


class Factory:
    def __init__(self, service):
        self.service = service
        self.installation_ids = []

    def build(self, *, installation_id):
        self.installation_ids.append(installation_id)
        return self.service

    def preview_configuration(self, *, installation_id):
        self.installation_ids.append(installation_id)
        return RouteWorkerConfigurationPreview(
            schemaVersion="aos.route-worker-configuration-preview/v1",
            status="needs_input",
            title="后台处理配置条件未齐",
            summary="当前不会自动处理业务；请先补齐配置条件。",
            approvalAllowed=False,
            checks=(
                RouteWorkerConfigurationCheck(
                    key="current_customer_installation",
                    label="当前客户安装",
                    passed=True,
                    detail="当前客户安装已确认。",
                ),
                RouteWorkerConfigurationCheck(
                    key="background_identity",
                    label="后台业务身份",
                    passed=False,
                    detail="后台业务身份待配置。",
                ),
                RouteWorkerConfigurationCheck(
                    key="protected_storage",
                    label="受保护保存位置",
                    passed=False,
                    detail="受保护保存位置待配置。",
                ),
                RouteWorkerConfigurationCheck(
                    key="identity_credential",
                    label="身份凭据",
                    passed=False,
                    detail="身份凭据待配置。",
                ),
            ),
            nextActions=("补齐后台业务身份和受保护保存位置。",),
            sideEffects=RouteWorkerConfigurationSideEffects(
                databaseWrite=False,
                configurationWrite=False,
                tokenRequest=False,
                businessProcessing=False,
                externalEffect=False,
            ),
            canProcessBusinessTasks=False,
            evaluatedAt=datetime(2026, 10, 30, 21, 29, tzinfo=UTC),
        )


def client(service: Service) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(ecommerce_workshop.router)
    app.dependency_overrides[require_principal] = lambda: Principal(
        subject="user:test",
        org_id="org-org",
        project_id="dev-project",
        roles=["admin"],
        markings=["public"],
    )
    app.dependency_overrides[ecommerce_workshop.get_ecommerce_workshop_read_catalog] = (
        Catalog
    )
    app.dependency_overrides[
        ecommerce_workshop.get_route_worker_business_entry_factory
    ] = lambda: Factory(service)
    return TestClient(app, raise_server_exceptions=False)


def test_business_status_and_commands_have_no_installation_parameters():
    service = Service()
    with client(service) as api:
        status = api.get("/v1/ecommerce-workshop/background-processing")
        configured = api.post(
            "/v1/ecommerce-workshop/background-processing/configure",
            headers={"Idempotency-Key": "configure-1"},
            json={},
        )
        disabled = api.post(
            "/v1/ecommerce-workshop/background-processing/disable",
            headers={"Idempotency-Key": "disable-1"},
            json={},
        )
        restored = api.post(
            "/v1/ecommerce-workshop/background-processing/restore",
            headers={"Idempotency-Key": "restore-1"},
            json={},
        )

    assert [
        status.status_code,
        configured.status_code,
        disabled.status_code,
        restored.status_code,
    ] == [200] * 4
    assert status.json()["status"]["title"] == "后台处理配置已就绪"
    assert [
        configured.json()["result"]["title"],
        disabled.json()["result"]["title"],
        restored.json()["result"]["title"],
    ] == [
        "后台处理配置已就绪",
        "后台处理已停用",
        "后台处理配置已恢复",
    ]
    rendered = str([status.json(), configured.json(), disabled.json(), restored.json()])
    for forbidden in (
        "installationId",
        "lockHash",
        "bundleId",
        "secretVersion",
        "token",
    ):
        assert forbidden not in rendered
    assert [call[1]["idempotency_key"] for call in service.calls] == [
        "configure-1",
        "disable-1",
        "restore-1",
    ]


def test_configuration_preview_is_read_only_business_semantics():
    service = Service()
    with client(service) as api:
        response = api.get(
            "/v1/ecommerce-workshop/background-processing/configuration-preview"
        )

    assert response.status_code == 200
    assert response.json()["preview"]["status"] == "needs_input"
    assert response.json()["preview"]["approvalAllowed"] is False
    assert response.json()["preview"]["canProcessBusinessTasks"] is False
    rendered = str(response.json())
    for forbidden in (
        "installationId",
        "revision",
        "etag",
        "lockHash",
        "secretVersion",
        "locator",
    ):
        assert forbidden not in rendered
    assert service.calls == []


def test_business_commands_reject_query_and_internal_body_parameters():
    service = Service()
    with client(service) as api:
        query = api.post(
            "/v1/ecommerce-workshop/background-processing/configure?installationId=x",
            headers={"Idempotency-Key": "configure-query"},
            json={},
        )
        body = api.post(
            "/v1/ecommerce-workshop/background-processing/configure",
            headers={"Idempotency-Key": "configure-body"},
            json={"installationId": "x"},
        )

    assert [query.status_code, body.status_code] == [400, 400]
    assert service.calls == []

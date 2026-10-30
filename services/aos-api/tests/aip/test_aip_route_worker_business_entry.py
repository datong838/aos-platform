from __future__ import annotations

from datetime import UTC, datetime

from aos_api.aip_route_worker_customer_lifecycle import (
    RouteWorkerCustomerReceipt,
)
from aos_api.aip_route_worker_identity import RouteWorkerIdentityConfig
from tests.aip.test_aip_route_worker_customer_lifecycle import State, service
from tests.aip.test_aip_route_worker_installation import document


def completion(action: str) -> dict:
    state, title = {
        "enable": ("configuration_ready", "后台处理配置已就绪"),
        "disable": ("disabled", "后台处理已停用"),
        "restore": ("configuration_ready", "后台处理配置已恢复"),
    }[action]
    return RouteWorkerCustomerReceipt(
        schemaVersion="aos.route-worker-customer-receipt/v1",
        receiptId="00000000-0000-0000-0000-000000000301",
        action=action,
        state=state,
        title=title,
        summary="业务结果已记录，运行开关仍保持关闭。",
        canProcessBusinessTasks=False,
        completedAt=datetime(2026, 10, 30, 21, 30, tzinfo=UTC),
    ).model_dump(mode="json", by_alias=True)


def test_status_uses_current_authority_and_never_exposes_installation_fields():
    lifecycle, *_ = service(state=State(document()))

    status = lifecycle.read_status()

    assert status.state == "configuration_ready"
    assert status.can_process_business_tasks is False
    wire = status.model_dump(mode="json", by_alias=True)
    rendered = str(wire)
    for forbidden in (
        "installationId",
        "revision",
        "etag",
        "lockHash",
        "bundleId",
        "signature",
        "secretVersion",
        "token",
    ):
        assert forbidden not in rendered


def test_absent_configuration_distinguishes_no_receipt_disable_and_drift():
    lifecycle, *_ = service()
    assert lifecycle.read_status().state == "unconfigured"

    lifecycle._latest_completion_reader = lambda: completion("disable")
    assert lifecycle.read_status().state == "disabled"

    lifecycle._latest_completion_reader = lambda: completion("enable")
    assert lifecycle.read_status().state == "needs_review"


def test_control_coordinates_ignore_missing_installed_file(monkeypatch):
    monkeypatch.setenv("AOS_AUTH_EXTERNAL_ONLY", "1")
    monkeypatch.setenv("AOS_AUTH_ALLOW_DEV", "0")
    monkeypatch.setenv("AOS_OIDC_ISSUER", "http://127.0.0.1:18449/realms/qyh")
    monkeypatch.setenv("AOS_OIDC_AUDIENCE", "aos-api")
    monkeypatch.setenv(
        "AOS_OIDC_TOKEN_URL",
        "http://127.0.0.1:18449/realms/qyh/protocol/openid-connect/token",
    )
    monkeypatch.setenv("AOS_ROUTE_WORKER_OIDC_CLIENT_ID", "aos-route-worker")
    monkeypatch.setenv("AOS_ROUTE_WORKER_OIDC_SUBJECT", "route-worker-subject")
    monkeypatch.setenv("AOS_ROUTE_WORKER_OIDC_SECRET_VERSION", "v1")
    monkeypatch.setenv("AOS_ROUTE_WORKER_IDENTITY_FILE", "/missing/identity.json")

    config = RouteWorkerIdentityConfig.from_control_env()

    assert config.client_id == "aos-route-worker"
    assert config.installation_document is None

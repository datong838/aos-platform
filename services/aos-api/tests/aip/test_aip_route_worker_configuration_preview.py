from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aos_api.aip_route_worker_customer_lifecycle_wiring import (
    RouteWorkerBusinessEntryFactory,
)
from aos_api.aip_route_worker_identity import RouteWorkerIdentityConfig
from tests.aip.test_aip_route_worker_installation import document


NOW = datetime(2026, 10, 31, 1, 40, tzinfo=UTC)
INSTALLATION_ID = "00000000-0000-0000-0000-000000000107"


class Secrets:
    def __init__(self, *, available: bool = True) -> None:
        self.available = available
        self.probes = []
        self.reads = 0

    def exists(self, locator) -> bool:
        self.probes.append(locator)
        return self.available

    def read(self, _locator):
        self.reads += 1
        raise AssertionError("configuration preview must never read secret payload")


class Authority:
    def __init__(self, *, available: bool = True) -> None:
        self.available = available
        self.installation_checks = []

    def assert_installation_current(self, installation_id: str) -> bool:
        self.installation_checks.append(installation_id)
        if not self.available:
            raise RuntimeError("internal installation detail must not escape")
        return True

    def build_document(self, *, config, installation_id):
        if not self.available:
            raise RuntimeError("internal installation detail must not escape")
        return document(
            installationId=installation_id,
            issuer=config.issuer,
            audience=config.audience,
            tokenEndpoint=config.token_endpoint,
            clientId=config.client_id,
            expectedSubject=config.expected_subject,
            secretVersion=config.secret_version,
        )


def config() -> RouteWorkerIdentityConfig:
    return RouteWorkerIdentityConfig(
        issuer="http://127.0.0.1:18448/realms/qyh-local",
        audience="aos-api",
        token_endpoint=(
            "http://127.0.0.1:18448/realms/qyh-local/"
            "protocol/openid-connect/token"
        ),
        client_id="aos-route-worker",
        expected_subject="service-account-aos-route-worker",
        secret_version="v1",
    )


def forbidden_connection(*_args, **_kwargs):
    raise AssertionError("configuration preview must not access command receipts")


def factory(
    tmp_path,
    *,
    secrets=None,
    authority=None,
    config_factory=config,
    path=None,
    command_ready=lambda: True,
    post_enabled=lambda: True,
):
    return RouteWorkerBusinessEntryFactory(
        connect_factory=forbidden_connection,
        read_connect_factory=forbidden_connection,
        secret_client=secrets or Secrets(),
        authority_factory=lambda: authority or Authority(),
        config_factory=config_factory,
        path_factory=lambda: path or (tmp_path / "route-worker.json"),
        command_readiness_probe=command_ready,
        configuration_post_enabled=post_enabled,
        clock=lambda: NOW,
    )


def test_configuration_preview_is_business_only_and_has_no_side_effects(tmp_path):
    secrets = Secrets()
    authority = Authority()

    preview = factory(
        tmp_path, secrets=secrets, authority=authority
    ).preview_configuration(installation_id=INSTALLATION_ID)

    assert preview.status == "reviewable"
    assert preview.approval_allowed is True
    assert [item.passed for item in preview.checks] == [True, True, True, True, True]
    assert preview.can_process_business_tasks is False
    assert preview.side_effects.model_dump(mode="json", by_alias=True) == {
        "databaseWrite": False,
        "configurationWrite": False,
        "tokenRequest": False,
        "businessProcessing": False,
        "externalEffect": False,
    }
    assert secrets.reads == 0
    assert len(secrets.probes) == 1
    assert authority.installation_checks == [INSTALLATION_ID]
    rendered = str(preview.model_dump(mode="json", by_alias=True))
    for forbidden in (
        "installationId",
        "revision",
        "etag",
        "lockHash",
        "secretVersion",
        "locator",
        str(tmp_path),
    ):
        assert forbidden not in rendered


@pytest.mark.parametrize(
    "missing", ["installation", "identity", "path", "secret", "submission"]
)
def test_configuration_preview_reports_missing_business_condition_without_raising(
    tmp_path, missing
):
    authority = Authority(available=missing != "installation")
    secrets = Secrets(available=missing != "secret")

    def config_factory():
        if missing == "identity":
            raise RuntimeError("internal identity coordinates")
        return config()

    def path_factory():
        if missing == "path":
            raise RuntimeError("internal path")
        return tmp_path / "route-worker.json"

    preview = RouteWorkerBusinessEntryFactory(
        connect_factory=forbidden_connection,
        read_connect_factory=forbidden_connection,
        secret_client=secrets,
        authority_factory=lambda: authority,
        config_factory=config_factory,
        path_factory=path_factory,
        command_readiness_probe=lambda: missing != "submission",
        configuration_post_enabled=lambda: True,
        clock=lambda: NOW,
    ).preview_configuration(installation_id=INSTALLATION_ID)

    assert preview.status == "needs_input"
    assert preview.approval_allowed is False
    assert preview.can_process_business_tasks is False
    assert any(not item.passed for item in preview.checks)
    assert preview.next_actions
    assert secrets.reads == 0
    assert "internal" not in str(preview.model_dump(mode="json", by_alias=True))


def test_configuration_preview_requires_explicit_post_gate(tmp_path):
    probes = []

    preview = factory(
        tmp_path,
        command_ready=lambda: probes.append("database") or True,
        post_enabled=lambda: False,
    ).preview_configuration(installation_id=INSTALLATION_ID)

    assert preview.status == "needs_input"
    assert preview.approval_allowed is False
    assert preview.checks[-1].label == "配置保存通道"
    assert preview.checks[-1].passed is False
    assert probes == []


def test_configuration_preview_rejects_unsafe_configuration_parent(tmp_path):
    unsafe = tmp_path / "shared"
    unsafe.mkdir(mode=0o777)
    unsafe.chmod(0o777)

    preview = factory(tmp_path, path=unsafe / "route-worker.json").preview_configuration(
        installation_id=INSTALLATION_ID
    )

    assert preview.status == "needs_input"
    assert preview.approval_allowed is False
    assert preview.checks[2].label == "受保护保存位置"
    assert preview.checks[2].passed is False

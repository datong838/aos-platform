from aos_api.aip_route_worker_customer_lifecycle_wiring import (
    RouteWorkerBusinessEntryFactory,
)
from aos_api.aip_route_worker_lifecycle_command_connection import (
    connect_route_worker_lifecycle_command,
)
from aos_api.aip_secret_backend import DeferredMountedSecretFileClient


class Secrets:
    def read(self, _locator):
        return "unused"

    def exists(self, _locator):
        return True


def test_default_customer_lifecycle_backend_uses_platform_factory(monkeypatch):
    secrets = Secrets()
    monkeypatch.setattr(
        "aos_api.aip_route_worker_customer_lifecycle_wiring.default_secret_client",
        lambda: secrets,
    )

    factory = RouteWorkerBusinessEntryFactory(
        connect_factory=lambda: None,
        read_connect_factory=lambda: None,
        authority_factory=lambda: None,
        config_factory=lambda: None,
    )

    assert factory._secret_client is secrets


def test_default_command_receipt_connection_is_dedicated():
    factory = RouteWorkerBusinessEntryFactory(
        read_connect_factory=lambda: None,
        authority_factory=lambda: None,
        config_factory=lambda: None,
    )

    assert factory._connect_factory is connect_route_worker_lifecycle_command


def test_linux_status_factory_constructs_before_secret_is_mounted(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.delenv("AOS_SECRET_MOUNT_ROOT", raising=False)

    factory = RouteWorkerBusinessEntryFactory(
        connect_factory=lambda: None,
        read_connect_factory=lambda: None,
        authority_factory=lambda: None,
        config_factory=lambda: None,
    )

    assert isinstance(factory._secret_client, DeferredMountedSecretFileClient)


def test_linux_unconfigured_status_does_not_require_secret_mount(tmp_path, monkeypatch):
    class ReadConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, *_args, **_kwargs):
            return self

        def fetchall(self):
            return []

    class Authority:
        def assert_current(self, _document):
            return True

    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.delenv("AOS_SECRET_MOUNT_ROOT", raising=False)
    factory = RouteWorkerBusinessEntryFactory(
        connect_factory=lambda: None,
        read_connect_factory=ReadConnection,
        authority_factory=Authority,
        config_factory=lambda: None,
        path_factory=lambda: tmp_path / "not-installed.json",
    )

    status = factory.build(installation_id="unused-until-configure").read_status()

    assert status.state == "unconfigured"
    assert status.title == "后台处理尚未配置"
    assert status.can_process_business_tasks is False

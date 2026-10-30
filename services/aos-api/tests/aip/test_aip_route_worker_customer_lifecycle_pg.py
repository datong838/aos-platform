from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from aos_api.aip_route_worker_customer_lifecycle import (
    RouteWorkerCustomerLifecycleBlocked,
    RouteWorkerCustomerLifecycleService,
)
from aos_api.aip_route_worker_customer_lifecycle_wiring import (
    RouteWorkerBusinessEntryFactory,
)
from aos_api.aip_route_worker_installation import (
    RouteWorkerIdentityInstallationStore,
)
from aos_api.aip_route_worker_installation_authority import (
    RouteWorkerSignedInstallationCoordinator,
)
from aos_api.asset_registry.errors import IdempotencyConflictError
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.db import connect
from tests.aip.test_aip_route_worker_installation import document

pytestmark = pytest.mark.skipif(
    os.getenv("AOS_ROUTE_WORKER_NATIVE_PG") != "1",
    reason="requires an explicit isolated Route-worker PostgreSQL window",
)

SCOPE = ("org-org", "dev-project")
PREPARE = "route_worker_identity.customer_lifecycle.prepare"
COMPLETE = "route_worker_identity.customer_lifecycle.complete"


class Secrets:
    def exists(self, locator) -> bool:
        return locator.account.endswith("client-secret/v1")

    def read(self, locator):
        raise AssertionError("native recovery must not read a secret payload")


class Authority:
    def assert_current(self, value) -> bool:
        assert value == document()
        return True


class CountingCoordinator:
    def __init__(self, delegate, effects: list[str]) -> None:
        self._delegate = delegate
        self._effects = effects

    def install(self, *args, **kwargs):
        result = self._delegate.install(*args, **kwargs)
        self._effects.append("install")
        return result

    def uninstall(self, *args, **kwargs):
        result = self._delegate.uninstall(*args, **kwargs)
        self._effects.append("uninstall")
        return result


class FailFirstCompletion:
    def __init__(self, delegate: PostgresInstallationStore) -> None:
        self._delegate = delegate
        self.failed = False

    def execute_idempotent(self, **kwargs):
        if kwargs["operation"] == COMPLETE and not self.failed:
            self.failed = True
            raise RuntimeError("injected process exit before completion receipt")
        return self._delegate.execute_idempotent(**kwargs)


def _assert_isolated_database() -> None:
    assert os.getenv("AOS_TEST_USE_SHARED_DATABASE") != "1"
    with connect() as conn:
        assert conn.info.host in {"127.0.0.1", "localhost"}
        assert conn.info.port not in {5432, 5433}
        assert conn.info.dbname.startswith("aos_test_")
        assert conn.info.dbname.endswith("_ti4_test")


def _ensure_positive_workspace() -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO twa_org (id,name) VALUES (%s,%s) ON CONFLICT (id) DO NOTHING",
            (SCOPE[0], "栖月汇原生恢复测试组织"),
        )
        conn.execute(
            "INSERT INTO twa_workspace (org_id,project_id,name) VALUES (%s,%s,%s) "
            "ON CONFLICT (org_id,project_id) DO NOTHING",
            (*SCOPE, "栖月汇原生恢复测试工作区"),
        )
        conn.execute(
            "INSERT INTO meta_org (id,name) VALUES (%s,%s) ON CONFLICT (id) DO NOTHING",
            (SCOPE[0], "栖月汇原生恢复权威组织"),
        )
        conn.execute(
            "INSERT INTO meta_workspace (org_id,project_id,name) VALUES (%s,%s,%s) "
            "ON CONFLICT (org_id,project_id) DO NOTHING",
            (*SCOPE, "栖月汇原生恢复权威工作区"),
        )
        conn.commit()


def _current_reader(path: Path):
    def read():
        try:
            path.lstat()
        except FileNotFoundError:
            return None
        return RouteWorkerIdentityInstallationStore.load(path)

    return read


def _service(
    *,
    receipt_store,
    path: Path,
    effects: list[str],
    latest_completion_reader=None,
) -> RouteWorkerCustomerLifecycleService:
    authority = Authority()
    file_store = RouteWorkerIdentityInstallationStore(secret_client=Secrets())
    coordinator = CountingCoordinator(
        RouteWorkerSignedInstallationCoordinator(
            store=file_store,
            authority=authority,
        ),
        effects,
    )
    return RouteWorkerCustomerLifecycleService(
        receipt_store=receipt_store,
        coordinator=coordinator,
        authority=authority,
        current_reader=_current_reader(path),
        document_factory=document,
        config_path=path,
        latest_completion_reader=latest_completion_reader,
        clock=lambda: datetime(2026, 10, 30, 15, 50, tzinfo=UTC),
        uuid_factory=uuid4,
    )


def _invoke(service, action: str, *, key: str, actor: str = "operator-1"):
    return getattr(service, action)(
        org_id=SCOPE[0],
        project_id=SCOPE[1],
        actor=actor,
        roles=("asset-installer",),
        idempotency_key=key,
    )


def _command_rows(key: str):
    with connect() as conn:
        apply_asset_transaction_scope(conn, org_id=SCOPE[0], project_id=SCOPE[1])
        return conn.execute(
            """
            SELECT operation, idempotency_key, subject, request_hash,
                   status_code, response_json
              FROM bundle_installation_command
             WHERE org_id = %s AND project_id = %s AND idempotency_key = %s
             ORDER BY operation
            """,
            (*SCOPE, key),
        ).fetchall()


def _latest_completion_reader():
    factory = RouteWorkerBusinessEntryFactory(
        connect_factory=connect,
        secret_client=Secrets(),
        authority_factory=lambda: Authority(),
        config_factory=lambda: None,
        path_factory=lambda: Path("/private/unused-in-read-test"),
    )
    return factory._latest_completion


def test_native_prepare_file_effect_restart_and_completion_recovery(tmp_path):
    _assert_isolated_database()
    _ensure_positive_workspace()
    path = tmp_path / "route-worker.json"
    effects: list[str] = []
    postgres = PostgresInstallationStore(connect_factory=connect)
    first_process = _service(
        receipt_store=FailFirstCompletion(postgres),
        path=path,
        effects=effects,
    )

    with pytest.raises(RuntimeError, match="process exit before completion receipt"):
        _invoke(first_process, "enable", key="g7k-native-enable-1")

    assert path.exists()
    assert oct(path.stat().st_mode & 0o777) == "0o600"
    assert RouteWorkerIdentityInstallationStore.load(path) == document()
    assert effects == ["install"]
    assert [row["operation"] for row in _command_rows("g7k-native-enable-1")] == [
        PREPARE
    ]

    second_process = _service(
        receipt_store=postgres,
        path=path,
        effects=effects,
        latest_completion_reader=_latest_completion_reader(),
    )
    recovered = _invoke(second_process, "enable", key="g7k-native-enable-1")
    replayed = _invoke(second_process, "enable", key="g7k-native-enable-1")

    assert recovered == replayed
    assert recovered.title == "后台处理配置已就绪"
    assert recovered.can_process_business_tasks is False
    assert effects == ["install"]
    rows = _command_rows("g7k-native-enable-1")
    assert [row["operation"] for row in rows] == [COMPLETE, PREPARE]
    assert {row["subject"] for row in rows} == {"operator-1"}
    assert len({row["request_hash"] for row in rows}) == 1
    assert second_process.read_status().state == "configuration_ready"

    with pytest.raises(IdempotencyConflictError):
        _invoke(second_process, "restore", key="g7k-native-enable-1")
    with pytest.raises(IdempotencyConflictError):
        _invoke(
            second_process,
            "enable",
            key="g7k-native-enable-1",
            actor="other-operator",
        )
    with pytest.raises(RouteWorkerCustomerLifecycleBlocked):
        second_process.enable(
            org_id="dev-org",
            project_id="dev-project",
            actor="operator-1",
            roles=("asset-installer",),
            idempotency_key="g7k-native-enable-1",
        )
    assert _command_rows("g7k-native-enable-1") == rows
    assert effects == ["install"]


def test_native_disabled_status_survives_process_restart(tmp_path):
    _assert_isolated_database()
    _ensure_positive_workspace()
    path = tmp_path / "route-worker.json"
    effects: list[str] = []
    file_store = RouteWorkerIdentityInstallationStore(secret_client=Secrets())
    file_store.install(path, document())
    postgres = PostgresInstallationStore(connect_factory=connect)
    first_process = _service(receipt_store=postgres, path=path, effects=effects)

    disabled = _invoke(first_process, "disable", key="g7k-native-disable-1")

    assert disabled.state == "disabled"
    assert not path.exists()
    assert effects == ["uninstall"]
    assert [row["operation"] for row in _command_rows("g7k-native-disable-1")] == [
        COMPLETE,
        PREPARE,
    ]

    latest_completion_reader = _latest_completion_reader()
    assert latest_completion_reader()["action"] == "disable"
    restarted = _service(
        receipt_store=postgres,
        path=path,
        effects=effects,
        latest_completion_reader=latest_completion_reader,
    )
    status = restarted.read_status()
    wire = status.model_dump(mode="json", by_alias=True)

    assert status.state == "disabled"
    assert status.title == "后台处理已停用"
    assert status.can_process_business_tasks is False
    assert all(
        field not in str(wire)
        for field in ("installationId", "lockHash", "secretVersion", "token")
    )

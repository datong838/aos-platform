from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from psycopg.pq import TransactionStatus

from aos_api.asset_registry.control_policy import DISABLE_RUNTIME_OPERATION
from aos_api.asset_registry.control_wiring import (
    RuntimeControlPlane,
    build_production_runtime_host_selection,
)
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.aip_runtime_configuration_sources import (
    build_current_configuration_authorization,
)
from aos_api.extension_runtime.configuration_consumer import ConfigurationConsumer
from aos_api.extension_runtime.configuration_authorization import (
    ConfigurationAuthorization,
    CurrentConfigurationPermission,
    CurrentFourSourceConfigurationAuthorization,
    CURRENT_FOUR_SOURCE_AUTHORITIES,
    _mint_current_four_source_authorization,
)
from aos_api.extension_runtime.current_permission import CurrentControlPermission
from aos_api.extension_runtime.disable_consumer import RuntimeDisableConsumer
from aos_api.extension_runtime.generation_attempts import (
    ExpiredSignedReadAttemptRecovery,
    GenerationDrainReader,
)
from aos_api.extension_runtime.oci_driver import CleanupOnlyOciDriver, OciDriver
from aos_api.extension_runtime.production_runtime import (
    RuntimeHostSelection,
    RuntimeWorkerDependencies,
    select_production_runtime_host,
)
from aos_api.extension_runtime.resource_recovery import ExpiredResourceRecovery
from aos_api.extension_runtime.runtime_identity import RuntimeDatabaseIdentity
from aos_api.ecommerce_growth_lifecycle import EcommerceGrowthDisableDependent


class _Transaction:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class _Connection:
    def __init__(self, name, rows=()):
        self.name = name
        self.rows = rows
        self.info = SimpleNamespace(transaction_status=TransactionStatus.IDLE)

    def transaction(self):
        return _Transaction()

    def execute(self, statement):
        assert "extension_runtime_read_host_assignments" in statement
        return self

    def fetchall(self):
        return list(self.rows)


def _connector(name, calls, rows=()):
    @contextmanager
    def connect():
        calls.append(name)
        yield _Connection(name, rows)

    return connect


def _identity(name, oid, *, directory=False, runtime=False):
    return RuntimeDatabaseIdentity(
        authority=("127.0.0.1", 5432, "aos"),
        session_user=name,
        role_oid=oid,
        directory_member=directory,
        runtime_member=runtime,
        privileged=False,
        owns_protected_relation=False,
    )


def _dependencies():
    return RuntimeWorkerDependencies(
        installation_store=PostgresInstallationStore(),
        configuration_authorize=build_current_configuration_authorization(
            permission=CurrentConfigurationPermission(
                installation_store=PostgresInstallationStore()
            )
        ),
        disable_permission=CurrentControlPermission(
            operation=DISABLE_RUNTIME_OPERATION
        ),
        drain_reader=GenerationDrainReader(),
        cleanup_driver=CleanupOnlyOciDriver(
            OciDriver(context="colima-aos-extension")
        ),
        disable_dependent=EcommerceGrowthDisableDependent(),
    )


def _patch_identities(monkeypatch, overrides=None):
    identities = {
        "directory": _identity("directory", 1, directory=True),
        "runtime": _identity("runtime", 2, runtime=True),
        "web": _identity("web", 3),
    }
    identities.update(overrides or {})
    monkeypatch.setattr(
        "aos_api.extension_runtime.production_runtime.probe_runtime_database_identity",
        lambda conn, **_: identities[conn.name],
    )


@pytest.mark.parametrize(
    ("enabled", "dependencies", "connector", "code"),
    [
        (False, _dependencies(), "valid", "DISABLED"),
        (True, None, "valid", "MISSING_DEPENDENCIES"),
        (True, _dependencies(), "invalid", "MISSING_DEPENDENCIES"),
    ],
)
def test_incomplete_selector_is_inactive_before_any_connection(
    enabled, dependencies, connector, code
):
    calls = []
    valid = _connector("unexpected", calls)
    selected = select_production_runtime_host(
        enabled=enabled,
        directory_connect=valid if connector == "valid" else None,
        runtime_connect=valid,
        web_connect=valid,
        dependencies=dependencies,
    )
    assert selected == RuntimeHostSelection(None, "INACTIVE", code)
    assert calls == []


def test_empty_directory_is_inactive_without_runtime_web_or_oci(monkeypatch):
    _patch_identities(monkeypatch)
    calls = []
    selected = select_production_runtime_host(
        enabled=True,
        directory_connect=_connector("directory", calls),
        runtime_connect=_connector("runtime", calls),
        web_connect=_connector("web", calls),
        dependencies=_dependencies(),
    )
    assert selected == RuntimeHostSelection(None, "INACTIVE", "DIRECTORY_EMPTY")
    assert calls == ["directory"]


def test_directory_identity_failure_stops_before_reading_other_planes(monkeypatch):
    _patch_identities(
        monkeypatch,
        {"directory": _identity("directory", 1, runtime=True)},
    )
    calls = []
    selected = select_production_runtime_host(
        enabled=True,
        directory_connect=_connector("directory", calls, ({
            "org_id": "org-org", "project_id": "dev-project", "assignment_revision": 1,
        },)),
        runtime_connect=_connector("runtime", calls),
        web_connect=_connector("web", calls),
        dependencies=_dependencies(),
    )
    assert selected.error_code == "DIRECTORY_PREFLIGHT_FAILED"
    assert calls == ["directory"]


def test_complete_selector_builds_only_concrete_workers_and_reuses_assignment(monkeypatch):
    _patch_identities(monkeypatch)
    calls = []
    rows = ({
        "org_id": "org-org", "project_id": "dev-project", "assignment_revision": 7,
    },)
    selected = select_production_runtime_host(
        enabled=True,
        directory_connect=_connector("directory", calls, rows),
        runtime_connect=_connector("runtime", calls),
        web_connect=_connector("web", calls),
        dependencies=_dependencies(),
    )
    assert selected.status == "ACTIVE" and selected.error_code is None
    assert calls == ["directory", "runtime", "web"]
    first = selected.host._current_assignments()[0]
    second = selected.host._current_assignments()[0]
    assert first is second
    assert type(first.recovery) is ExpiredResourceRecovery
    assert type(first.attempt_recovery) is ExpiredSignedReadAttemptRecovery
    assert tuple(type(value) for value in first.consumers) == (
        ConfigurationConsumer,
        RuntimeDisableConsumer,
    )
    assert type(first.consumers[1].executor.dependent) is EcommerceGrowthDisableDependent
    assert calls == ["directory", "runtime", "web", "directory", "directory"]


def test_three_plane_mismatch_returns_fixed_inactive_result(monkeypatch):
    _patch_identities(
        monkeypatch,
        {"runtime": _identity("directory", 1, runtime=True)},
    )
    calls = []
    rows = ({
        "org_id": "org-org", "project_id": "dev-project", "assignment_revision": 1,
    },)
    selected = select_production_runtime_host(
        enabled=True,
        directory_connect=_connector("directory", calls, rows),
        runtime_connect=_connector("runtime", calls),
        web_connect=_connector("web", calls),
        dependencies=_dependencies(),
    )
    assert selected == RuntimeHostSelection(
        None, "INACTIVE", "IDENTITY_PREFLIGHT_FAILED"
    )
    assert calls == ["directory", "runtime", "web"]


def test_three_plane_mismatch_constructs_zero_workers(monkeypatch):
    _patch_identities(
        monkeypatch,
        {"runtime": _identity("directory", 1, runtime=True)},
    )
    constructed = []

    def recovery(**kwargs):
        constructed.append(kwargs)
        return object()

    monkeypatch.setattr(
        "aos_api.extension_runtime.production_runtime.ExpiredResourceRecovery",
        recovery,
    )
    rows = ({
        "org_id": "org-org", "project_id": "dev-project", "assignment_revision": 1,
    },)
    selected = select_production_runtime_host(
        enabled=True,
        directory_connect=_connector("directory", [], rows),
        runtime_connect=_connector("runtime", []),
        web_connect=_connector("web", []),
        dependencies=_dependencies(),
    )
    assert selected.error_code == "IDENTITY_PREFLIGHT_FAILED"
    assert constructed == []


@pytest.mark.parametrize(
    "authorize",
    [
        lambda **_: True,
        ConfigurationAuthorization(permission=lambda **_: True, readers={}),
        build_current_configuration_authorization(permission=lambda **_: True),
    ],
)
def test_selector_rejects_non_four_source_authority_before_connections(authorize):
    calls = []
    with pytest.raises(TypeError, match="four-source"):
        RuntimeWorkerDependencies(
            installation_store=PostgresInstallationStore(),
            configuration_authorize=authorize,
            disable_permission=CurrentControlPermission(
                operation=DISABLE_RUNTIME_OPERATION
            ),
            drain_reader=GenerationDrainReader(),
            cleanup_driver=CleanupOnlyOciDriver(
                OciDriver(context="colima-aos-extension")
            ),
            disable_dependent=EcommerceGrowthDisableDependent(),
        )
    assert calls == []


def test_exact_four_source_type_rejects_fake_permission_and_readers():
    fake_readers = {
        key: (lambda *_args, **_kwargs: True)
        for key in CURRENT_FOUR_SOURCE_AUTHORITIES
    }
    with pytest.raises(TypeError, match="AIP factory"):
        CurrentFourSourceConfigurationAuthorization(
            permission=lambda **_: True,
            readers=fake_readers,
        )
    with pytest.raises(TypeError):
        _mint_current_four_source_authorization(
            permission=CurrentConfigurationPermission(
                installation_store=PostgresInstallationStore()
            ),
            readers=fake_readers,
        )


def test_environment_wiring_stays_zero_access_until_all_values_exist(monkeypatch):
    for name in (
        "AOS_EXTENSION_RUNTIME_HOST_ENABLED",
        "AOS_EXTENSION_RUNTIME_DATABASE_URL",
        "AOS_EXTENSION_DIRECTORY_DATABASE_URL",
        "AOS_EXTENSION_OCI_CONTEXT",
    ):
        monkeypatch.delenv(name, raising=False)
    selected = build_production_runtime_host_selection(
        control_plane=RuntimeControlPlane(None, None, None, None, None, None)
    )
    assert selected == RuntimeHostSelection(None, "INACTIVE", "DISABLED")


def test_environment_wiring_constructs_exact_dependencies_without_starting(monkeypatch):
    monkeypatch.setenv("AOS_EXTENSION_RUNTIME_HOST_ENABLED", "1")
    monkeypatch.setenv("AOS_EXTENSION_RUNTIME_DATABASE_URL", "runtime-dsn")
    monkeypatch.setenv("AOS_EXTENSION_DIRECTORY_DATABASE_URL", "directory-dsn")
    monkeypatch.setenv("AOS_EXTENSION_OCI_CONTEXT", "colima-aos-extension")
    captured = {}

    def select(**kwargs):
        captured.update(kwargs)
        return RuntimeHostSelection(None, "INACTIVE", "TEST_CAPTURE")

    monkeypatch.setattr(
        "aos_api.extension_runtime.production_runtime.select_production_runtime_host",
        select,
    )
    authorize = build_current_configuration_authorization(
        permission=CurrentConfigurationPermission(
            installation_store=PostgresInstallationStore()
        )
    )
    dependent = EcommerceGrowthDisableDependent()
    plane = RuntimeControlPlane(
        PostgresInstallationStore(), None, None, None, None, authorize,
        disable_dependent=dependent,
    )
    selected = build_production_runtime_host_selection(control_plane=plane)
    assert selected.error_code == "TEST_CAPTURE"
    assert captured["enabled"] is True
    dependencies = captured["dependencies"]
    assert type(dependencies) is RuntimeWorkerDependencies
    assert dependencies.configuration_authorize is authorize
    assert type(dependencies.drain_reader) is GenerationDrainReader
    assert type(dependencies.cleanup_driver) is CleanupOnlyOciDriver
    assert dependencies.disable_dependent is dependent

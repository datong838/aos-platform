from contextlib import contextmanager
import json
from types import SimpleNamespace

import pytest
from psycopg.pq import TransactionStatus

from aos_api.asset_registry.control_policy import (
    APPLY_INSTALLATION_OPERATION,
    DISABLE_RUNTIME_OPERATION,
    ENABLE_RUNTIME_OPERATION,
    VERIFY_INSTALLATION_OPERATION,
)
from aos_api.asset_registry.control_wiring import (
    RuntimeControlPlane,
    build_production_runtime_host_selection,
    build_runtime_control_plane,
)
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.release_policy import ReleasePolicy
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
from aos_api.extension_runtime.production_preparation import (
    ProductionPreparationDependencies,
)
from aos_api.extension_runtime.production_runtime import (
    RuntimeHostSelection,
    RuntimeWorkerDependencies,
    select_production_runtime_host,
)
from aos_api.extension_runtime.live_job_directory import LivePreparedJobDirectory
from aos_api.extension_runtime.live_installation_scheduler import LiveInstallationScheduler
from aos_api.extension_runtime.release_revalidation import RuntimeReleaseRevalidator
from aos_api.extension_runtime.resource_recovery import ExpiredResourceRecovery
from aos_api.extension_runtime.runtime_identity import RuntimeDatabaseIdentity
from aos_api.ecommerce_growth_lifecycle import EcommerceGrowthDisableDependent


class _Transaction:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def test_production_control_plane_owns_one_empty_live_job_directory():
    first = build_runtime_control_plane(disable_dependent=EcommerceGrowthDisableDependent())
    second = build_runtime_control_plane(disable_dependent=EcommerceGrowthDisableDependent())
    assert type(first.live_job_directory) is LivePreparedJobDirectory
    assert type(second.live_job_directory) is LivePreparedJobDirectory
    assert first.live_job_directory is not second.live_job_directory


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


def _dependencies(runtime_connect):
    store = PostgresInstallationStore()
    authorize = build_current_configuration_authorization(
        permission=CurrentConfigurationPermission(installation_store=store)
    )
    policy = ReleasePolicy(trust_roots=None)
    driver = OciDriver(context="colima-aos-extension")
    preparation = ProductionPreparationDependencies(
        connect=runtime_connect,
        installation_store=store,
        revalidator=RuntimeReleaseRevalidator(release_policy=policy),
        policy=policy,
        loader=ManifestLoader({}, trust_roots=None),
        apply_permission=CurrentControlPermission(
            operation=APPLY_INSTALLATION_OPERATION
        ),
        verification_permission=CurrentControlPermission(
            operation=VERIFY_INSTALLATION_OPERATION
        ),
        enable_permission=CurrentControlPermission(operation=ENABLE_RUNTIME_OPERATION),
        configuration_authorize=authorize,
        driver=driver,
        platform="linux/arm64",
        live_directory=LivePreparedJobDirectory(),
    )
    return RuntimeWorkerDependencies(
        installation_store=store,
        configuration_authorize=authorize,
        disable_permission=CurrentControlPermission(
            operation=DISABLE_RUNTIME_OPERATION
        ),
        drain_reader=GenerationDrainReader(),
        cleanup_driver=CleanupOnlyOciDriver(driver),
        disable_dependent=EcommerceGrowthDisableDependent(),
        preparation=preparation,
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
    ("enabled", "has_dependencies", "connector", "code"),
    [
        (False, True, "valid", "DISABLED"),
        (True, False, "valid", "MISSING_DEPENDENCIES"),
        (True, True, "invalid", "MISSING_DEPENDENCIES"),
    ],
)
def test_incomplete_selector_is_inactive_before_any_connection(
    enabled, has_dependencies, connector, code
):
    calls = []
    valid = _connector("unexpected", calls)
    dependencies = _dependencies(valid) if has_dependencies else None
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
    runtime_connect = _connector("runtime", calls)
    selected = select_production_runtime_host(
        enabled=True,
        directory_connect=_connector("directory", calls),
        runtime_connect=runtime_connect,
        web_connect=_connector("web", calls),
        dependencies=_dependencies(runtime_connect),
    )
    assert selected == RuntimeHostSelection(None, "INACTIVE", "DIRECTORY_EMPTY")
    assert calls == ["directory"]


def test_mismatched_runtime_connector_is_inactive_before_any_connection():
    calls = []
    verified_runtime = _connector("runtime", calls)
    other_runtime = _connector("other-runtime", calls)
    selected = select_production_runtime_host(
        enabled=True,
        directory_connect=_connector("directory", calls),
        runtime_connect=verified_runtime,
        web_connect=_connector("web", calls),
        dependencies=_dependencies(other_runtime),
    )
    assert selected == RuntimeHostSelection(
        None, "INACTIVE", "MISMATCHED_RUNTIME_CONNECTOR"
    )
    assert calls == []


def test_directory_identity_failure_stops_before_reading_other_planes(monkeypatch):
    _patch_identities(
        monkeypatch,
        {"directory": _identity("directory", 1, runtime=True)},
    )
    calls = []
    runtime_connect = _connector("runtime", calls)
    selected = select_production_runtime_host(
        enabled=True,
        directory_connect=_connector("directory", calls, ({
            "org_id": "org-org", "project_id": "dev-project", "assignment_revision": 1,
        },)),
        runtime_connect=runtime_connect,
        web_connect=_connector("web", calls),
        dependencies=_dependencies(runtime_connect),
    )
    assert selected.error_code == "DIRECTORY_PREFLIGHT_FAILED"
    assert calls == ["directory"]


def test_complete_selector_builds_only_concrete_workers_and_reuses_assignment(monkeypatch):
    _patch_identities(monkeypatch)
    calls = []
    rows = ({
        "org_id": "org-org", "project_id": "dev-project", "assignment_revision": 7,
    },)
    runtime_connect = _connector("runtime", calls)
    selected = select_production_runtime_host(
        enabled=True,
        directory_connect=_connector("directory", calls, rows),
        runtime_connect=runtime_connect,
        web_connect=_connector("web", calls),
        dependencies=_dependencies(runtime_connect),
    )
    assert selected.status == "ACTIVE" and selected.error_code is None
    assert calls == ["directory", "runtime", "web"]
    first = selected.host._current_assignments()[0]
    second = selected.host._current_assignments()[0]
    assert first is second
    assert type(first.recovery) is ExpiredResourceRecovery
    assert type(first.attempt_recovery) is ExpiredSignedReadAttemptRecovery
    assert type(first.lifecycle) is LiveInstallationScheduler
    assert first.lifecycle.directory.scope == first.scope
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
    runtime_connect = _connector("runtime", calls)
    selected = select_production_runtime_host(
        enabled=True,
        directory_connect=_connector("directory", calls, rows),
        runtime_connect=runtime_connect,
        web_connect=_connector("web", calls),
        dependencies=_dependencies(runtime_connect),
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
    runtime_connect = _connector("runtime", [])
    selected = select_production_runtime_host(
        enabled=True,
        directory_connect=_connector("directory", [], rows),
        runtime_connect=runtime_connect,
        web_connect=_connector("web", []),
        dependencies=_dependencies(runtime_connect),
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
            preparation=object(),
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
    monkeypatch.setattr("aos_api.asset_registry.control_wiring._current_a0v_host_preflight",
                        lambda **_: pytest.fail("disabled Host accessed current preflight"), raising=False)
    for name in (
        "AOS_EXTENSION_RUNTIME_HOST_ENABLED",
        "AOS_EXTENSION_RUNTIME_DATABASE_URL",
        "AOS_EXTENSION_DIRECTORY_DATABASE_URL",
        "AOS_EXTENSION_OCI_CONTEXT",
        "AOS_EXTENSION_RUNTIME_PLATFORM",
    ):
        monkeypatch.delenv(name, raising=False)
    selected = build_production_runtime_host_selection(
        control_plane=RuntimeControlPlane(None, None, None, None, None, None)
    )
    assert selected == RuntimeHostSelection(None, "INACTIVE", "DISABLED")


def test_enabled_host_requires_current_signed_receipt_and_protected_file_before_selector(monkeypatch):
    monkeypatch.setenv("AOS_EXTENSION_RUNTIME_HOST_ENABLED", "1")
    monkeypatch.setenv("AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE", "/protected/current-identities.json")
    monkeypatch.delenv("AOS_CURRENT_SIGNED_RECEIPT", raising=False)
    monkeypatch.setattr(
        "aos_api.extension_runtime.production_runtime.select_production_runtime_host",
        lambda **_: pytest.fail("selector reached without current signed receipt"),
    )
    selected = build_production_runtime_host_selection(
        control_plane=RuntimeControlPlane(None, None, None, None, None, None)
    )
    assert selected == RuntimeHostSelection(None, "INACTIVE", "CURRENT_SIGNED_HOST_PREFLIGHT_REQUIRED")


def test_enabled_host_failed_current_preflight_stops_before_selector(monkeypatch):
    monkeypatch.setenv("AOS_EXTENSION_RUNTIME_HOST_ENABLED", "1")
    monkeypatch.setenv("AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE", "/protected/old-identities.json")
    monkeypatch.setenv("AOS_CURRENT_SIGNED_RECEIPT", "/current/signing-receipt.json")
    monkeypatch.setattr("aos_api.asset_registry.control_wiring._current_a0v_host_preflight",
                        lambda **_: False, raising=False)
    monkeypatch.setattr(
        "aos_api.extension_runtime.production_runtime.select_production_runtime_host",
        lambda **_: pytest.fail("selector reached after failed current preflight"),
    )
    selected = build_production_runtime_host_selection(
        control_plane=RuntimeControlPlane(None, None, None, None, None, None)
    )
    assert selected == RuntimeHostSelection(None, "INACTIVE", "CURRENT_SIGNED_HOST_PREFLIGHT_FAILED")


def test_enabled_host_does_not_accept_legacy_dsn_pair_without_protected_file(monkeypatch):
    monkeypatch.setenv("AOS_EXTENSION_RUNTIME_HOST_ENABLED", "1")
    monkeypatch.setenv("AOS_CURRENT_SIGNED_RECEIPT", "/current/signing-receipt.json")
    monkeypatch.delenv("AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE", raising=False)
    monkeypatch.setenv("AOS_EXTENSION_RUNTIME_DATABASE_URL", "old-runtime")
    monkeypatch.setenv("AOS_EXTENSION_DIRECTORY_DATABASE_URL", "old-directory")
    monkeypatch.setattr("aos_api.asset_registry.control_wiring._current_a0v_host_preflight",
                        lambda **_: pytest.fail("legacy DSNs reached current preflight"))
    assert build_production_runtime_host_selection(
        control_plane=RuntimeControlPlane(None, None, None, None, None, None)
    ) == RuntimeHostSelection(None, "INACTIVE", "CURRENT_SIGNED_HOST_PREFLIGHT_REQUIRED")


def test_current_host_preflight_requires_api_physical_authority_and_signed_paths(monkeypatch, tmp_path):
    from aos_api.asset_registry import control_wiring as wiring
    signed_root = tmp_path / "signed-bundles"
    signed_root.mkdir()
    trust = tmp_path / "trust-roots.json"
    trust.write_text("{}")
    monkeypatch.setenv("AOS_BUNDLE_ROOT", str(signed_root))
    monkeypatch.setenv("AOS_BUNDLE_TRUST_ROOTS_FILE", str(trust))
    authority = ["172.0.0.2", 5432, "aos_current_preview_20260927"]
    report = {"outcome": "CURRENT_SIGNED_HOST_READONLY_PREFLIGHT_GREEN",
              "authorization": "PREFLIGHT_ONLY_NO_RUNTIME_START",
              "scope": ["org-org", "dev-project"], "databaseAuthority": authority,
              "signedRoot": str(signed_root), "trustRoots": str(trust),
              "credentialFileGeneration": [1, 2, 3, 4, 5]}
    monkeypatch.setattr(wiring.subprocess, "run", lambda *_a, **_k: SimpleNamespace(
        returncode=0, stdout="log line\n" + json.dumps(report)))
    monkeypatch.setattr("aos_api.db.get_dsn", lambda: "api-dsn")
    pins = []
    monkeypatch.setattr(
        "aos_api.extension_runtime.runtime_connections.pin_runtime_file_generation",
        lambda path, generation: pins.append((path, generation)),
    )

    class Conn:
        read_only = False
        database_name = "aos_current_preview_20260927"
        def __enter__(self): return self
        def __exit__(self, *_): return None
        def execute(self, _query):
            assert self.read_only is True
            return self
        def fetchone(self):
            return {"server_addr": "172.0.0.2", "server_port": 5432,
                    "database_name": self.database_name}

    connection = Conn()
    monkeypatch.setattr("psycopg.connect", lambda *_a, **_k: connection)
    inputs = {"signed_receipt": str(tmp_path / "receipt.json"),
              "credential_reference": str(tmp_path / "identities.json")}
    assert wiring._current_a0v_host_preflight(**inputs) is True
    assert pins == [(inputs["credential_reference"], [1, 2, 3, 4, 5])]
    monkeypatch.setattr(
        "aos_api.extension_runtime.runtime_connections.pin_runtime_file_generation",
        lambda *_: (_ for _ in ()).throw(RuntimeError("credential file changed")),
    )
    assert wiring._current_a0v_host_preflight(**inputs) is False
    connection.database_name = "old_same_name_drift"
    assert wiring._current_a0v_host_preflight(**inputs) is False
    connection.database_name = "aos_current_preview_20260927"
    other = tmp_path / "old-bundles"
    other.mkdir()
    monkeypatch.setenv("AOS_BUNDLE_ROOT", str(other))
    assert wiring._current_a0v_host_preflight(**inputs) is False


@pytest.mark.parametrize("returncode,output", [
    (2, '{"outcome":"SAFE_BLOCKED","reasonCode":"CREDENTIAL_DATABASE_DRIFT"}'),
    (0, "not-json"),
])
def test_current_host_preflight_subprocess_failure_never_opens_api_db(
    monkeypatch, tmp_path, returncode, output,
):
    from aos_api.asset_registry import control_wiring as wiring
    monkeypatch.setattr(wiring.subprocess, "run", lambda *_a, **_k: SimpleNamespace(
        returncode=returncode, stdout=output))
    monkeypatch.setattr("psycopg.connect", lambda *_a, **_k: pytest.fail("API DB opened"))
    assert wiring._current_a0v_host_preflight(
        signed_receipt=str(tmp_path / "receipt.json"),
        credential_reference=str(tmp_path / "identities.json"),
    ) is False


def test_environment_wiring_requires_platform_before_allowlist_access(monkeypatch):
    monkeypatch.setenv("AOS_EXTENSION_RUNTIME_HOST_ENABLED", "1")
    monkeypatch.setenv("AOS_CURRENT_SIGNED_RECEIPT", "/fixture/signed-receipt.json")
    monkeypatch.setenv("AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE", "/fixture/identities.json")
    monkeypatch.setattr("aos_api.asset_registry.control_wiring._current_a0v_host_preflight",
                        lambda **_: True)
    monkeypatch.setenv("AOS_EXTENSION_RUNTIME_DATABASE_URL", "runtime-dsn")
    monkeypatch.setenv("AOS_EXTENSION_DIRECTORY_DATABASE_URL", "directory-dsn")
    monkeypatch.setenv("AOS_EXTENSION_OCI_CONTEXT", "colima-aos-extension")
    monkeypatch.delenv("AOS_EXTENSION_RUNTIME_PLATFORM", raising=False)
    monkeypatch.setattr(
        "aos_api.asset_registry.control_wiring._allowlist_roots",
        lambda **_: (_ for _ in ()).throw(AssertionError("allowlist accessed")),
    )
    selected = build_production_runtime_host_selection(
        control_plane=RuntimeControlPlane(None, None, None, None, None, None)
    )
    assert selected == RuntimeHostSelection(
        None, "INACTIVE", "MISSING_DEPENDENCIES"
    )


def test_environment_wiring_rejects_unsupported_platform(monkeypatch):
    monkeypatch.setenv("AOS_EXTENSION_RUNTIME_HOST_ENABLED", "1")
    monkeypatch.setenv("AOS_CURRENT_SIGNED_RECEIPT", "/fixture/signed-receipt.json")
    monkeypatch.setenv("AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE", "/fixture/identities.json")
    monkeypatch.setattr("aos_api.asset_registry.control_wiring._current_a0v_host_preflight",
                        lambda **_: True)
    monkeypatch.setenv("AOS_EXTENSION_RUNTIME_DATABASE_URL", "runtime-dsn")
    monkeypatch.setenv("AOS_EXTENSION_DIRECTORY_DATABASE_URL", "directory-dsn")
    monkeypatch.setenv("AOS_EXTENSION_OCI_CONTEXT", "colima-aos-extension")
    monkeypatch.setenv("AOS_EXTENSION_RUNTIME_PLATFORM", "darwin/arm64")
    store = PostgresInstallationStore()
    authorize = build_current_configuration_authorization(
        permission=CurrentConfigurationPermission(installation_store=store)
    )
    selected = build_production_runtime_host_selection(
        control_plane=RuntimeControlPlane(
            store,
            None,
            None,
            None,
            None,
            authorize,
            disable_dependent=EcommerceGrowthDisableDependent(),
            live_job_directory=LivePreparedJobDirectory(),
        )
    )
    assert selected == RuntimeHostSelection(
        None, "INACTIVE", "MISSING_DEPENDENCIES"
    )


@pytest.mark.parametrize('stage_flag', ['0', '1', 'invalid'])
def test_environment_wiring_constructs_exact_dependencies_without_starting(monkeypatch, stage_flag):
    monkeypatch.setenv('AOS_EXTENSION_RUNTIME_CONFIGURATION_STAGE_ENABLED', stage_flag)
    monkeypatch.setenv("AOS_EXTENSION_RUNTIME_HOST_ENABLED", "1")
    monkeypatch.setenv("AOS_CURRENT_SIGNED_RECEIPT", "/fixture/signed-receipt.json")
    monkeypatch.setenv('AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE', '/fixture/path/validated-by-identity-selector')
    monkeypatch.setattr("aos_api.asset_registry.control_wiring._current_a0v_host_preflight",
                        lambda **_: True)
    monkeypatch.setenv("AOS_EXTENSION_OCI_CONTEXT", "colima-aos-extension")
    monkeypatch.setenv("AOS_EXTENSION_RUNTIME_PLATFORM", "linux/arm64")
    captured = {}

    def select(**kwargs):
        captured.update(kwargs)
        return RuntimeHostSelection(None, "INACTIVE", "TEST_CAPTURE")

    monkeypatch.setattr(
        "aos_api.extension_runtime.production_runtime.select_production_runtime_host",
        select,
    )
    store = PostgresInstallationStore()
    authorize = build_current_configuration_authorization(
        permission=CurrentConfigurationPermission(
            installation_store=store
        )
    )
    dependent = EcommerceGrowthDisableDependent()
    plane = RuntimeControlPlane(
        store, None, None, None, None, authorize,
        disable_dependent=dependent,
        live_job_directory=LivePreparedJobDirectory(),
    )
    selected = build_production_runtime_host_selection(control_plane=plane)
    assert selected.error_code == "TEST_CAPTURE"
    assert captured["enabled"] is True
    dependencies = captured["dependencies"]
    if stage_flag == "invalid":
        assert dependencies is None
        return
    assert dependencies.configuration_stage_enabled is (stage_flag == "1")
    assert type(dependencies) is RuntimeWorkerDependencies
    assert dependencies.configuration_authorize is authorize
    assert type(dependencies.drain_reader) is GenerationDrainReader
    assert type(dependencies.cleanup_driver) is CleanupOnlyOciDriver
    assert dependencies.disable_dependent is dependent
    assert type(dependencies.preparation) is ProductionPreparationDependencies
    assert dependencies.preparation.connect is captured["runtime_connect"]
    assert dependencies.preparation.live_directory is plane.live_job_directory

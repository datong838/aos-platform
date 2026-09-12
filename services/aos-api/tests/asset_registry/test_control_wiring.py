"""Production wiring tests for the M2-B shared control seam."""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from aos_api.asset_registry import control_wiring
from aos_api.asset_registry.control_protocols import (
    ActiveBaselineReader,
    CompositionControl,
    IdempotentCommandHandler,
    IdempotentCommandStore,
    InstallationControl,
)
from aos_api.asset_registry.signature import TrustRootConfigurationError


def test_importing_wiring_does_not_import_future_b1_services() -> None:
    package_root = Path(__file__).resolve().parents[2]
    script = f"""
import json
import sys
sys.path.insert(0, {str(package_root)!r})
import aos_api.asset_registry.control_wiring
targets = [
    "aos_api.asset_registry.composition_service",
    "aos_api.asset_registry.installation_service",
    "aos_api.asset_registry.installation_revalidation",
    "aos_api.asset_registry.installation_store",
]
print("CONTROL_WIRING_RESULT=" + json.dumps(
    {{name: name in sys.modules for name in targets}}, sort_keys=True
))
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )
    result_line = next(
        line
        for line in completed.stdout.splitlines()
        if line.startswith("CONTROL_WIRING_RESULT=")
    )
    loaded = json.loads(result_line.removeprefix("CONTROL_WIRING_RESULT="))
    assert loaded == {
        "aos_api.asset_registry.composition_service": False,
        "aos_api.asset_registry.installation_revalidation": False,
        "aos_api.asset_registry.installation_service": False,
        "aos_api.asset_registry.installation_store": False,
    }


def test_control_protocol_signatures_match_the_frozen_parallel_contract() -> None:
    expected = {
        IdempotentCommandHandler.__call__: (
            ("self", "conn"),
            (),
            "CommandResult",
        ),
        IdempotentCommandStore.execute_idempotent: (
            ("self",),
            (
                "org_id",
                "project_id",
                "operation",
                "idempotency_key",
                "subject",
                "request_hash",
                "handler",
            ),
            "CommandReceipt",
        ),
        CompositionControl.resolve: (
            ("self",),
            (
                "request",
                "org_id",
                "project_id",
                "actor",
                "roles",
                "markings",
                "idempotency_key",
            ),
            "CommandReceipt",
        ),
        CompositionControl.get_lock: (
            ("self",),
            (
                "org_id",
                "project_id",
                "composition_id",
                "revision",
                "roles",
                "markings",
            ),
            "StoredCompositionLock",
        ),
        ActiveBaselineReader.load_active_baseline_in_transaction: (
            ("self", "conn"),
            ("org_id", "project_id", "requested_ref"),
            "ActiveInstallationBaseline",
        ),
        InstallationControl.create: (
            ("self",),
            (
                "request",
                "org_id",
                "project_id",
                "actor",
                "roles",
                "markings",
                "idempotency_key",
            ),
            "CommandReceipt",
        ),
        InstallationControl.list: (
            ("self",),
            ("query", "org_id", "project_id", "roles", "markings"),
            "InstallationListResponse",
        ),
        InstallationControl.get: (
            ("self",),
            (
                "installation_id",
                "org_id",
                "project_id",
                "roles",
                "markings",
            ),
            "InstallationResponse",
        ),
    }
    action_requests = {
        InstallationControl.submit: "EmptyInstallationActionRequest",
        InstallationControl.approve: "ApproveInstallationRequest",
        InstallationControl.reject: "RejectInstallationRequest",
        InstallationControl.apply: "EmptyInstallationActionRequest",
        InstallationControl.verify: "EmptyInstallationActionRequest",
        InstallationControl.rollback: "RollbackInstallationRequest",
    }
    for method, request_annotation in action_requests.items():
        expected[method] = (
            ("self",),
            (
                "installation_id",
                "request",
                "org_id",
                "project_id",
                "actor",
                "roles",
                "markings",
                "idempotency_key",
                "if_match",
            ),
            "CommandReceipt",
        )
        assert method.__annotations__["request"] == request_annotation

    for method, (positional, keyword_only, return_annotation) in expected.items():
        signature = inspect.signature(method)
        parameters = tuple(signature.parameters.values())
        assert (
            tuple(
                item.name
                for item in parameters
                if item.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
            )
            == positional
        )
        assert (
            tuple(
                item.name
                for item in parameters
                if item.kind is inspect.Parameter.KEYWORD_ONLY
            )
            == keyword_only
        )
        assert all(item.default is inspect.Parameter.empty for item in parameters)
        assert signature.return_annotation == return_annotation


def test_registry_builder_uses_only_server_controlled_roots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repository"
    catalog_root = repository_root / "bundles"
    server_root = tmp_path / "server-bundles"
    catalog_root.mkdir(parents=True)
    server_root.mkdir()
    captured: dict[str, Any] = {}

    class StoreSpy:
        pass

    class LoaderSpy:
        def __init__(
            self,
            allowlist_roots: dict[str, Path],
            trust_roots: object | None = None,
        ) -> None:
            captured["allowlist_roots"] = allowlist_roots
            captured["trust_roots"] = trust_roots
            self.trust_roots = trust_roots

    monkeypatch.delenv("AOS_BUNDLE_TRUST_ROOTS_FILE", raising=False)
    monkeypatch.setenv("AOS_BUNDLE_ROOT", str(server_root))

    service = control_wiring.build_asset_registry_service(
        repository_root=repository_root,
        registry_store_factory=StoreSpy,
        manifest_loader_factory=LoaderSpy,
    )

    assert service._store.__class__ is StoreSpy
    assert captured == {
        "allowlist_roots": {
            "catalog": catalog_root,
            "server": server_root,
            "a0v-canonical": server_root,
        },
        "trust_roots": None,
    }


def test_registry_builder_does_not_expose_server_aliases_without_configuration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repository"
    catalog_root = repository_root / "bundles"
    catalog_root.mkdir(parents=True)
    monkeypatch.delenv("AOS_BUNDLE_ROOT", raising=False)

    assert control_wiring._allowlist_roots(repository_root=repository_root) == {
        "catalog": catalog_root
    }


def test_invalid_trust_root_configuration_is_deferred_and_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing-trust-roots.json"
    monkeypatch.setenv("AOS_BUNDLE_TRUST_ROOTS_FILE", str(missing))
    provider = control_wiring._configured_trust_roots()

    assert provider is not None
    with pytest.raises(TrustRootConfigurationError):
        provider.get_trust_root(publisher="publisher", key_id="key")


def test_runtime_view_production_wiring_uses_read_only_installation_and_ui_resolver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aos_api.db import connect_read_only
    from aos_api.extension_runtime.ui_resources import ProductionUiSessionResolver

    monkeypatch.delenv("AOS_EXTENSION_UI_RESOURCE_ORIGIN", raising=False)
    installation = control_wiring._build_read_only_installation_service()
    resolver = control_wiring._build_runtime_ui_session_resolver()

    assert installation._store._connect_factory is connect_read_only
    assert isinstance(resolver, ProductionUiSessionResolver)


def test_control_builders_load_future_modules_only_when_called(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: dict[str, Any] = {}

    class FakeCompositionService:
        def __init__(self, **kwargs: Any) -> None:
            created["composition"] = kwargs

    class FakeInstallationService:
        def __init__(self, **kwargs: Any) -> None:
            created["installation"] = kwargs

    class FakeRevalidator:
        def __init__(self, **kwargs: Any) -> None:
            created["revalidator"] = kwargs

    class FakeRuntimeUninstallGuard:
        pass

    modules = {
        "aos_api.asset_registry.composition_service": (
            "CompositionService",
            FakeCompositionService,
        ),
        "aos_api.asset_registry.installation_service": (
            "InstallationService",
            FakeInstallationService,
        ),
        "aos_api.asset_registry.installation_revalidation": (
            "InstallationRevalidator",
            FakeRevalidator,
        ),
        "aos_api.extension_runtime.runtime_uninstall": (
            "RuntimeUninstallGuard",
            FakeRuntimeUninstallGuard,
        ),
    }
    for name, (attribute, value) in modules.items():
        module = ModuleType(name)
        setattr(module, attribute, value)
        monkeypatch.setitem(sys.modules, name, module)

    composition = control_wiring.build_composition_service()
    installation = control_wiring.build_installation_service()

    assert composition.__class__ is FakeCompositionService
    assert installation.__class__ is FakeInstallationService
    assert set(created["composition"]) == {
        "snapshot_reader",
        "composition_store",
        "command_store",
        "baseline_reader",
    }
    assert (
        created["composition"]["command_store"]
        is created["composition"]["baseline_reader"]
    )
    assert set(created["installation"]) == {
        "store",
        "composition_store",
        "revalidator",
        "runtime_uninstall_guard",
    }
    assert created["installation"]["revalidator"].__class__ is FakeRevalidator
    assert created["installation"]["runtime_uninstall_guard"].__class__ is FakeRuntimeUninstallGuard
    assert set(created["revalidator"]) == {"release_policy"}


def test_runtime_control_plane_uses_one_store_and_formal_configuration_sources() -> None:
    from aos_api.aip_runtime_configuration_sources import (
        DATA_AUTHORITY,
        POLICY_AUTHORITY,
        ROLE_AUTHORITY,
    )
    from aos_api.ecommerce_growth_lifecycle import EcommerceGrowthDisableDependent
    from aos_api.extension_runtime.runtime_uninstall import RuntimeUninstallGuard

    dependent = EcommerceGrowthDisableDependent()
    plane = control_wiring.build_runtime_control_plane(disable_dependent=dependent)
    canonical_installation = control_wiring.build_installation_service()

    assert plane.lifecycle_service._store is plane.installation_store
    assert plane.configuration_service._store is plane.installation_store
    assert plane.lifecycle_service._reader is plane.installation_reader
    assert plane.configuration_service._reader is plane.installation_reader
    assert plane.lifecycle_service._revalidator is plane.revalidator
    assert plane.configuration_service._revalidator is plane.revalidator
    assert plane.configuration_service._authorize is plane.configuration_authorize
    assert plane.disable_service._dependent is dependent
    assert plane.disable_dependent is dependent
    assert type(plane.installation_reader._runtime_uninstall_guard) is RuntimeUninstallGuard
    assert type(canonical_installation._runtime_uninstall_guard) is RuntimeUninstallGuard
    assert set(plane.configuration_authorize._readers) == {
        ("role", ROLE_AUTHORITY),
        ("data", DATA_AUTHORITY),
        ("budget", "aip.budget_revision"),
        ("policy", POLICY_AUTHORITY),
    }


def test_runtime_control_plane_permission_locks_the_current_installation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aos_api.asset_registry.control_policy import CONFIGURE_RUNTIME_OPERATION
    from aos_api.extension_runtime import current_permission as permission_module

    calls: dict[str, Any] = {}
    locked = object()

    class PermissionSpy:
        def __init__(self, *, operation: str) -> None:
            calls["operation"] = operation

        def __call__(self, *, conn: Any, locked: Any, actor: str) -> bool:
            calls["permission"] = (conn, locked, actor)
            return True

    class Result:
        @staticmethod
        def fetchone() -> dict[str, int]:
            return {"etag_version": 7}

    class Connection:
        @staticmethod
        def execute(statement: str, parameters: tuple[str, str, str]) -> Result:
            calls["query"] = (statement, parameters)
            return Result()

    monkeypatch.setattr(permission_module, "CurrentControlPermission", PermissionSpy)
    plane = control_wiring.build_runtime_control_plane()

    def lock_for_transition(
        _self: Any,
        conn: Any,
        *,
        org_id: str,
        project_id: str,
        installation_id: str,
        expected_etag_version: int,
    ) -> object:
        calls["lock"] = (
            conn,
            org_id,
            project_id,
            installation_id,
            expected_etag_version,
        )
        return locked

    monkeypatch.setattr(
        type(plane.installation_store),
        "lock_for_transition_in_transaction",
        lock_for_transition,
    )
    conn = Connection()

    assert plane.configuration_authorize._permission(
        conn,
        org_id="org-org",
        project_id="dev-project",
        installation_id="00000000-0000-0000-0000-000000000001",
        generation="00000000-0000-0000-0000-000000000002",
        actor="operator@example.test",
    ) is True
    assert calls["operation"] == CONFIGURE_RUNTIME_OPERATION
    assert calls["query"][1] == (
        "org-org",
        "dev-project",
        "00000000-0000-0000-0000-000000000001",
    )
    assert calls["lock"] == (
        conn,
        "org-org",
        "dev-project",
        "00000000-0000-0000-0000-000000000001",
        7,
    )
    assert calls["permission"] == (conn, locked, "operator@example.test")


def test_first_registration_requires_explicit_connection_and_construction_is_idle():
    from aos_api.ecommerce_growth_registration import FirstDispatchRegistrationService
    assert control_wiring.build_runtime_control_plane().first_dispatch_registration_service is None
    def connect():
        pytest.fail('construction must not open a connection')
    plane=control_wiring.build_runtime_control_plane(registration_connect=connect)
    service=plane.first_dispatch_registration_service
    assert type(service) is FirstDispatchRegistrationService
    assert service._connect is connect and service._store is plane.installation_store
    assert service._authorize is plane.configuration_authorize
    with pytest.raises(TypeError):control_wiring.build_runtime_control_plane(registration_connect='not-a-connection')

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
print(json.dumps({{name: name in sys.modules for name in targets}}, sort_keys=True))
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )
    loaded = json.loads(completed.stdout.strip().splitlines()[-1])
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
        "allowlist_roots": {"catalog": catalog_root, "server": server_root},
        "trust_roots": None,
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
    }
    assert created["installation"]["revalidator"].__class__ is FakeRevalidator
    assert set(created["revalidator"]) == {"release_policy"}

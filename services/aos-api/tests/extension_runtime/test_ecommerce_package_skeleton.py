import importlib.util
from pathlib import Path
import re
import sys

import pytest
import yaml

from aos_api.asset_registry.contracts import BundleManifest
from aos_api.extension_runtime.contracts import RegistrationDescription


ROOT = Path(__file__).resolve().parents[4]
SDK_ROOT = ROOT / "packages/aos-extension-sdk/python"
PACKAGES = (
    ("bundles/domains/ecommerce-core", "ecommerce_core", "ecommerce_core_object_describe"),
    ("bundles/solutions/ecommerce-growth", "ecommerce_growth", "ecommerce_growth_investigation_describe"),
    ("bundles/platforms/ecommerce-niushop", "ecommerce_niushop", "ecommerce_niushop_source_describe"),
)


def _module(base, package):
    path = ROOT / base / "backend" / package / "__init__.py"
    spec = importlib.util.spec_from_file_location(f"ar2_{package}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("base,package,operation", PACKAGES)
def test_bundle_runtime_registration_is_exact_and_inactive(base, package, operation):
    manifest = BundleManifest.model_validate(yaml.safe_load((ROOT / base / "bundle.yaml").read_text()))
    runtime = manifest.spec.runtime.backend
    assert runtime.entrypoint == f"backend/{package}/__init__.py:register"
    assert runtime.python_package == package
    module = _module(base, package)
    registration = module.register(object())
    RegistrationDescription.model_validate(registration)
    assert [item["operationId"] for item in registration["contributions"]] == [operation]
    with pytest.raises(PermissionError, match="registration-only"):
        module.handle(operation, {}, object())
    with pytest.raises(ValueError):
        module.handle("unknown.operation", {}, object())


def test_dispatch_ref_is_immutable_and_forwarded_without_authority_override():
    sys.path.insert(0, str(SDK_ROOT))
    try:
        from aos_extension_sdk.dispatch import DispatchRef, commit_with_dispatch
    finally:
        sys.path.remove(str(SDK_ROOT))
    payload = {
        "orgId": "org-org",
        "projectId": "dev-project",
        "operationId": "ecommerce_niushop_source_describe",
        "handlerKind": "extension",
        "dispatchRevision": 3,
        "installationId": "11111111-1111-4111-8111-111111111111",
        "generation": "22222222-2222-4222-8222-222222222222",
        "executionEpoch": 4,
        "cutoverGroupId": "33333333-3333-4333-8333-333333333333",
        "cutoverGroupRevision": 5,
    }
    dispatch_ref = DispatchRef.from_payload(payload)
    with pytest.raises(AttributeError):
        dispatch_ref.handler_kind = "legacy"

    class Port:
        def commit(self, *, dispatch_ref, command):
            assert dispatch_ref.to_payload() == payload
            return dict(command)

    assert commit_with_dispatch(Port(), dispatch_ref, {"requestId": "r1"}) == {"requestId": "r1"}
    with pytest.raises(ValueError, match="cannot override"):
        commit_with_dispatch(Port(), dispatch_ref, {"nested": {"orgId": "other"}})
    with pytest.raises(ValueError):
        DispatchRef.from_payload({**payload, "dispatchRevision": 0})
    with pytest.raises(ValueError):
        DispatchRef.from_payload({**payload, "orgId": "other", "extra": True})
    legacy = DispatchRef.from_payload({
        **payload,
        "handlerKind": "legacy",
        "installationId": None,
        "generation": None,
        "executionEpoch": None,
    })
    assert legacy.installation_id is None
    with pytest.raises(ValueError, match="cannot claim"):
        DispatchRef.from_payload({**payload, "handlerKind": "legacy"})


def test_bundle_backend_has_no_platform_imports():
    for base, package, _operation in PACKAGES:
        text = (ROOT / base / "backend" / package / "__init__.py").read_text()
        assert "aos_api" not in text


def test_dispatch_authority_migration_is_empty_tenant_scoped_and_retained():
    path = ROOT / "services/aos-api/alembic/versions/ar2_001_ecommerce_dispatch_authority.py"
    text = path.read_text()
    assert 'down_revision = "ar1_004"' in text
    assert "CREATE TABLE extension_operation_dispatch_binding" in text
    assert "PRIMARY KEY(org_id, project_id, operation_id)" in text
    operation_id_contract = r"^[A-Za-z][A-Za-z0-9_]*$"
    assert "operation_id ~ '^[A-Za-z][A-Za-z0-9_]*$'" in text
    assert re.fullmatch(operation_id_contract, "ecommerce_niushop_source_describe")
    assert not re.fullmatch(operation_id_contract, "bad.operation")
    assert not re.fullmatch(operation_id_contract, " bad")
    assert "handler_kind text" in text
    assert "updated_by text NOT NULL" in text
    assert "handler_kind='legacy' AND installation_id IS NULL" in text
    assert "handler_kind='extension' AND installation_id IS NOT NULL" in text
    assert "ENABLE ROW LEVEL SECURITY" in text
    assert "FORCE ROW LEVEL SECURITY" in text
    assert "GRANT SELECT ON extension_operation_dispatch_binding TO aos_runtime" in text
    assert "INSERT INTO extension_operation_dispatch_binding" not in text
    assert 'raise RuntimeError("operation dispatch authority must be retained")' in text

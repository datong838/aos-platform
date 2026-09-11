"""Source qualification for the versioned ecommerce runtime candidates."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.extension_runtime.contracts import RegistrationDescription


ROOT = Path(__file__).resolve().parents[4]
CANDIDATE_ROOT = ROOT / "bundles/candidates/ecommerce"
CASES = (
    (
        "domain.ecommerce.core/1.1.0",
        "bundles/domains/ecommerce-core",
        "domain.ecommerce.core",
        "1.1.0",
        "ecommerce_core",
        ("ecommerce_core_object_describe",),
    ),
    (
        "platform.ecommerce.niushop/1.1.0",
        "bundles/platforms/ecommerce-niushop",
        "platform.ecommerce.niushop",
        "1.1.0",
        "ecommerce_niushop",
        ("ecommerce_niushop_source_describe", "ecommerce_niushop_facts_read"),
    ),
    (
        "solution.ecommerce.growth/1.5.0",
        "bundles/solutions/ecommerce-growth",
        "solution.ecommerce.growth",
        "1.5.0",
        "ecommerce_growth",
        (
            "ecommerce_growth_investigation_describe",
            "ecommerce_growth_case_put",
            "ecommerce_growth_schedule_put",
            "ecommerce_growth_schedule_trigger",
            "ecommerce_growth_data_fulfill",
            "ecommerce_growth_analysis_advance",
            "ecommerce_growth_review_advance",
            "ecommerce_growth_content_generate",
            "ecommerce_growth_content_review",
        ),
    ),
)


def _python_tree(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*.py"))
        if "__pycache__" not in path.parts
    }


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        raw = path.read_bytes()
        digest.update(str(path.relative_to(root)).encode("utf-8") + b"\0")
        digest.update(str(len(raw)).encode("ascii") + b"\0")
        digest.update(raw)
    return digest.hexdigest()


def test_immutable_1_4_0_candidate_keeps_exact_historical_hashes() -> None:
    legacy = CANDIDATE_ROOT / "solution.ecommerce.growth/1.4.0"
    assert _tree_hash(legacy) == "4dc6cfbeadc2c50d9bcdbaf85fc78b0aa9f8174db525c696e6c23dadcfaf43b3"
    assert _tree_hash(legacy / "backend") == "959f154b717d31c3d09451a2dde9d837993d69aa85be5c7c23afe06cee555649"


def test_current_1_5_0_candidate_keeps_exact_reviewed_source_hash() -> None:
    candidate = CANDIDATE_ROOT / "solution.ecommerce.growth/1.5.0"
    assert _tree_hash(candidate) == "34446fcbfc1a8b7239cc44cdb4d801584d618deffbadc9c6bddaf7d69e5b0bd0"
    assert _tree_hash(candidate / "backend") == "0d9a0b6988c1ffbfb79ff4ab2389f4038d81385ab2735389a8a800901c85c302"


def test_growth_successor_preserves_registry_bundle_identity() -> None:
    loader = ManifestLoader({"candidate": CANDIDATE_ROOT})
    previous = loader.load("bundle://candidate/solution.ecommerce.growth/1.4.0")
    successor = loader.load("bundle://candidate/solution.ecommerce.growth/1.5.0")

    assert successor.manifest.metadata.display_name == previous.manifest.metadata.display_name


def _module(path: Path, package: str):
    entrypoint = path / "backend" / package / "__init__.py"
    spec = importlib.util.spec_from_file_location(f"candidate_{package}", entrypoint)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runtime_candidate_backends_are_exact_versioned_snapshots() -> None:
    for candidate_path, author_path, _bundle_id, _version, _package, _operations in CASES:
        candidate_backend = CANDIDATE_ROOT / candidate_path / "backend"
        author_backend = ROOT / author_path / "backend"
        assert _python_tree(candidate_backend) == _python_tree(author_backend)
        assert _python_tree(candidate_backend)


def test_runtime_candidate_manifests_and_registration_are_exact() -> None:
    loader = ManifestLoader({"candidate": CANDIDATE_ROOT})
    observed_operations: set[str] = set()
    for candidate_path, _author_path, bundle_id, version, package, operations in CASES:
        loaded = loader.load(f"bundle://candidate/{candidate_path}")
        manifest = loaded.manifest
        assert (manifest.metadata.id, manifest.metadata.version) == (bundle_id, version)
        assert manifest.spec.runtime is not None
        runtime = manifest.spec.runtime.backend
        assert runtime is not None
        assert runtime.entrypoint == f"backend/{package}/__init__.py:register"
        assert runtime.python_package == package
        assert runtime.image_index == "artifacts/runtime-image-index.json"
        registration = RegistrationDescription.model_validate(
            _module(CANDIDATE_ROOT / candidate_path, package).register(object())
        )
        actual = tuple(item.operation_id for item in registration.contributions)
        assert actual == operations
        assert observed_operations.isdisjoint(actual)
        observed_operations.update(actual)
    assert len(observed_operations) == 12


def test_candidate_composition_has_exact_versions_dependencies_and_eight_modules() -> None:
    loader = ManifestLoader({"candidate": CANDIDATE_ROOT})
    paths = (
        "domain.ecommerce.core/1.1.0",
        "platform.ecommerce.niushop/1.1.0",
        "solution.ecommerce.operations-base/1.2.0",
        "solution.ecommerce.growth/1.5.0",
    )
    loaded = [loader.load(f"bundle://candidate/{path}") for path in paths]
    coordinates = {(item.manifest.metadata.id, item.manifest.metadata.version) for item in loaded}
    assert coordinates == {
        ("domain.ecommerce.core", "1.1.0"),
        ("platform.ecommerce.niushop", "1.1.0"),
        ("solution.ecommerce.operations-base", "1.2.0"),
        ("solution.ecommerce.growth", "1.5.0"),
    }
    for item in loaded[1:]:
        dependencies = item.manifest.spec.dependencies
        assert len(dependencies) == 1
        dependency = dependencies[0]
        assert (dependency.publisher, dependency.id) == ("aos", "domain.ecommerce.core")
        assert dependency.version == ">=1.1.0 <2.0.0"
    modules = [module for item in loaded for module in item.workshop_modules]
    assert len(modules) == 8
    assert len({item.module_id for item in modules}) == 8
    assert len({item.route for item in modules}) == 8


def test_registration_handlers_remain_fail_closed_before_cutover() -> None:
    for candidate_path, _author_path, _bundle_id, _version, package, operations in CASES:
        module = _module(CANDIDATE_ROOT / candidate_path, package)
        for operation in operations:
            try:
                module.handle(operation, {}, object())
            except PermissionError as exc:
                assert "registration-only" in str(exc)
            else:
                raise AssertionError(f"candidate handler unexpectedly ran: {operation}")


def test_runtime_candidates_bind_exact_platform_schema_compatibility() -> None:
    expected_relations = [
        "public.asset_bundle",
        "public.asset_bundle_artifact",
        "public.asset_bundle_evidence",
        "public.asset_bundle_version",
        "public.bundle_composition",
        "public.bundle_composition_lock",
        "public.bundle_installation",
        "public.bundle_installation_revision",
        "public.extension_operation_dispatch_binding",
        "public.extension_runtime_binding",
        "public.extension_runtime_operation",
        "public.extension_runtime_resource_lease",
        "public.extension_schema_installation",
    ]
    for candidate_path, _author_path, bundle_id, _version, _package, _operations in CASES:
        artifacts = CANDIDATE_ROOT / candidate_path / "artifacts"
        compatibility_raw = (artifacts / "schema-compatibility.json").read_bytes()
        compatibility = json.loads(compatibility_raw)
        assert compatibility == {
            "schemaVersion": 1,
            "bundleId": bundle_id,
            "alembicRevision": "a0v_001",
            "noPackageOwnedMigration": True,
            "requiredRelations": expected_relations,
        }
        requirements = json.loads(
            (artifacts / "schema-requirements.json").read_bytes()
        )
        assert requirements == {
            "schemaVersion": 1,
            "requirements": [
                {
                    "version": "aos-platform-a0v-001",
                    "migrationHash": "sha256:"
                    + hashlib.sha256(compatibility_raw).hexdigest(),
                }
            ],
        }

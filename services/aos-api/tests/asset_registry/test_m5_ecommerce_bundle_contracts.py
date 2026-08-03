"""M5-0 contracts for unsigned, content-free ecommerce bundle skeletons."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml
from aos_api.asset_registry.contracts import BundleManifest
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.semver import satisfies

REPO_ROOT = Path(__file__).resolve().parents[4]
BUNDLES_ROOT = REPO_ROOT / "bundles"
MANIFEST_SCHEMA = (
    REPO_ROOT / "packages/contracts/schemas/asset-bundles/"
    "bundle-manifest-v1alpha1.schema.json"
)
CORE_ID = "domain.ecommerce.core"
CORE_DEPENDENCY = (("aos", CORE_ID, ">=1.0.0 <2.0.0"),)


@dataclass(frozen=True, slots=True)
class _BundleCase:
    relative_path: str
    bundle_id: str
    kind: str
    display_name: str
    dependencies: tuple[tuple[str, str, str], ...]
    exports: dict[str, tuple[str, ...]]


BUNDLE_CASES = (
    _BundleCase(
        relative_path="domains/ecommerce-core",
        bundle_id=CORE_ID,
        kind="DomainPack",
        display_name="Ecommerce Core Fixture",
        dependencies=(),
        exports={
            "ontology": ("content/ontology/",),
            "schemas": ("content/schemas/",),
            "policies": ("content/policies/",),
        },
    ),
    _BundleCase(
        relative_path="solutions/ecommerce-operations-base",
        bundle_id="solution.ecommerce.operations-base",
        kind="SolutionPack",
        display_name="Ecommerce Operations Base Fixture",
        dependencies=CORE_DEPENDENCY,
        exports={
            "logic": ("content/logic/",),
            "workshops": ("content/workshops/",),
            "evals": ("content/evals/",),
        },
    ),
    _BundleCase(
        relative_path="solutions/ecommerce-growth",
        bundle_id="solution.ecommerce.growth",
        kind="SolutionPack",
        display_name="Ecommerce Growth Fixture",
        dependencies=CORE_DEPENDENCY,
        exports={
            "agents": ("content/agents/",),
            "logic": ("content/logic/",),
            "workshops": ("content/workshops/",),
            "evals": ("content/evals/",),
            "policies": ("content/policies/",),
        },
    ),
    _BundleCase(
        relative_path="platforms/ecommerce-niushop",
        bundle_id="platform.ecommerce.niushop",
        kind="PlatformAdapterPack",
        display_name="Ecommerce Platform Adapter Fixture",
        dependencies=CORE_DEPENDENCY,
        exports={
            "connectors": ("content/connectors/",),
            "schemas": ("content/schemas/",),
            "mappings": ("content/mappings/",),
        },
    ),
)


def _manifest_payload(case: _BundleCase) -> dict:
    content = (BUNDLES_ROOT / case.relative_path / "bundle.yaml").read_text(
        encoding="utf-8"
    )
    payload = yaml.safe_load(content)
    assert isinstance(payload, dict)
    return payload


@pytest.mark.parametrize("case", BUNDLE_CASES, ids=lambda case: case.bundle_id)
def test_bundle_manifest_matches_frozen_contract_and_existing_exports(
    case: _BundleCase,
) -> None:
    payload = _manifest_payload(case)
    manifest = BundleManifest.model_validate(payload)

    assert manifest.api_version == "aos.dev/v1alpha1"
    assert manifest.kind.value == case.kind
    assert manifest.metadata.model_dump(by_alias=True) == {
        "id": case.bundle_id,
        "version": "1.0.0",
        "displayName": case.display_name,
        "publisher": "aos",
        "license": "internal",
    }
    assert manifest.spec.platform_api == ">=1.7.0 <2.0.0"
    assert satisfies("1.7.0", manifest.spec.platform_api)
    assert (
        tuple(
            (item.publisher, item.id, item.version)
            for item in manifest.spec.dependencies
        )
        == case.dependencies
    )
    assert all(satisfies("1.0.0", item.version) for item in manifest.spec.dependencies)
    assert manifest.spec.optional_dependencies == []
    assert manifest.spec.conflicts == []
    assert manifest.spec.capabilities.provides == []
    assert manifest.spec.capabilities.requires == []
    assert manifest.spec.permissions.model_dump(by_alias=True) == {
        "roles": [],
        "markings": [],
        "dataScopes": [],
        "actionTypes": [],
    }
    assert manifest.spec.migrations.plan is None
    assert manifest.spec.migrations.downgrade_policy.value == "retain-canonical"
    assert manifest.spec.preflight is None
    assert manifest.spec.regression is None
    assert manifest.spec.rollback is None
    assert manifest.spec.contributions == []

    actual_exports = {
        name: tuple(paths)
        for name, paths in manifest.spec.exports.model_dump().items()
        if paths
    }
    assert actual_exports == case.exports
    for paths in case.exports.values():
        for relative_path in paths:
            export_path = BUNDLES_ROOT / case.relative_path / relative_path
            assert export_path.is_dir()
            assert [item.name for item in export_path.iterdir()] == [".gitkeep"]
            assert (export_path / ".gitkeep").read_text(encoding="utf-8").strip() == ""


def test_shared_manifest_schema_remains_the_strict_dto_source_contract() -> None:
    schema = json.loads(MANIFEST_SCHEMA.read_text(encoding="utf-8"))
    generated = BundleManifest.model_json_schema(by_alias=True)

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["apiVersion", "kind", "metadata", "spec"]
    assert set(schema["properties"]) == set(generated["properties"])
    assert schema["$defs"]["metadata"]["additionalProperties"] is False
    assert schema["$defs"]["spec"]["additionalProperties"] is False


def test_three_leaf_bundles_depend_only_on_core() -> None:
    dependency_edges = {
        (dependency_id, case.bundle_id)
        for case in BUNDLE_CASES
        for _publisher, dependency_id, _version in case.dependencies
    }

    assert dependency_edges == {
        (CORE_ID, "solution.ecommerce.operations-base"),
        (CORE_ID, "solution.ecommerce.growth"),
        (CORE_ID, "platform.ecommerce.niushop"),
    }


@pytest.mark.parametrize("case", BUNDLE_CASES, ids=lambda case: case.bundle_id)
def test_real_loader_accepts_unsigned_skeleton_with_only_minimal_evidence(
    case: _BundleCase,
) -> None:
    loader = ManifestLoader({"m5-fixtures": BUNDLES_ROOT})
    source_ref = f"bundle://m5-fixtures/{case.relative_path}"

    first = loader.load(source_ref)
    second = loader.load(source_ref)

    assert first.manifest.metadata.id == case.bundle_id
    assert first.signature is None
    assert first.content_hash == second.content_hash
    assert first.artifacts == second.artifacts
    assert [item.relative_path for item in first.artifacts] == sorted(
        [
            *(f"{path}.gitkeep" for paths in case.exports.values() for path in paths),
            "evidence/bundle-evals.json",
            "evidence/sbom.json",
        ]
    )
    assert all(
        item.size == 1 if item.relative_path.endswith(".gitkeep") else item.size > 0
        for item in first.artifacts
    )
    assert {(item.type.value, item.status.value) for item in first.evidence} == {
        ("manifest_validation", "valid"),
        ("content_hash", "valid"),
        ("sbom", "valid"),
        ("bundle_evals", "valid"),
    }
    assert not (BUNDLES_ROOT / case.relative_path / "bundle.signature.json").exists()

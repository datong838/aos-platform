"""Contracts for unsigned ecommerce bundles with real exported artifacts."""

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
    version: str
    display_name: str
    dependencies: tuple[tuple[str, str, str], ...]
    exports: dict[str, tuple[str, ...]]
    capabilities: tuple[str, ...] = ()


BUNDLE_CASES = (
    _BundleCase(
        relative_path="domains/ecommerce-core",
        bundle_id=CORE_ID,
        kind="DomainPack",
        version="1.0.0",
        display_name="电商核心本体包",
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
        version="1.1.0",
        display_name="电商运营基础方案包",
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
        version="1.3.0",
        display_name="电商增长方案包（D3：W03 客户与私域运营台 + L05 分润异常检测）",
        dependencies=CORE_DEPENDENCY,
        exports={
            "agents": ("content/agents/",),
            "logic": ("content/logic/",),
            "workshops": ("content/workshops/",),
            "evals": ("content/evals/",),
            "policies": ("content/policies/",),
            "schemas": ("content/schemas/",),
        },
        capabilities=(
            "material.collect",
            "strategy.plan",
            "copy.generate",
            "script.compose",
            "speech.synthesize",
            "video.compose",
            "content.review",
            "live.orchestrate",
            "platform.adapt",
            "performance.review",
        ),
    ),
    _BundleCase(
        relative_path="platforms/ecommerce-niushop",
        bundle_id="platform.ecommerce.niushop",
        kind="PlatformAdapterPack",
        version="1.0.0",
        display_name="Niushop 微商城平台适配包",
        dependencies=CORE_DEPENDENCY,
        exports={
            "connectors": ("content/connectors/",),
            "schemas": ("content/schemas/",),
            "mappings": ("content/mappings/",),
            "policies": ("content/policies/",),
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
        "version": case.version,
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
    assert tuple(manifest.spec.capabilities.provides) == case.capabilities
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
    expected_claim_count = {
        "solution.ecommerce.operations-base": 2,
        "solution.ecommerce.growth": 14,
    }.get(case.bundle_id, 0)
    assert len(manifest.spec.contributions) == expected_claim_count

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
            assert any(
                item.is_file() and item.name != ".gitkeep"
                for item in export_path.rglob("*")
            )


def test_niushop_connector_and_source_readiness_policies_cover_p01_p12() -> None:
    root = BUNDLES_ROOT / "platforms/ecommerce-niushop/content"
    connector = json.loads(
        (root / "connectors/niushop-mysql.manifest.json").read_text(
            encoding="utf-8"
        )
    )
    freshness = json.loads(
        (root / "policies/source-freshness.v1.json").read_text(encoding="utf-8")
    )
    quality = json.loads(
        (root / "policies/source-quality.v1.json").read_text(encoding="utf-8")
    )
    reconciliation = json.loads(
        (root / "policies/source-reconciliation.v1.json").read_text(
            encoding="utf-8"
        )
    )

    assert connector["version"] == "0.1.1"
    assert connector["presets"]["tables"] == [
        "ns_site",
        "ns_goods",
        "ns_goods_sku",
        "ns_goods_category",
        "ns_order",
        "ns_order_goods",
        "ns_express_delivery_package",
        "ns_member",
        "ns_weapp",
        "ns_config",
        "ns_goods_evaluate",
        "ns_pay",
    ]
    assert freshness["expectedCronByPipeline"] == {
        f"P{index:02d}-{suffix}-qyh": f"0 {index + 1} * * *"
        for index, suffix in enumerate(
            (
                "shop",
                "product",
                "product-sku",
                "category",
                "order",
                "order-line",
                "shipment",
                "customer-lite",
                "weapp",
                "system-config",
                "product-review",
                "payment",
            ),
            start=1,
        )
    }
    assert quality["schemaVersion"] == "aos.source-readiness.quality-policy/v1"
    assert reconciliation["schemaVersion"] == (
        "aos.source-readiness.reconciliation-policy/v1"
    )


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
def test_real_loader_accepts_unsigned_bundle_with_stable_exported_artifacts(
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
    artifact_paths = [item.relative_path for item in first.artifacts]
    assert artifact_paths == sorted(artifact_paths)
    assert "evidence/bundle-evals.json" in artifact_paths
    assert "evidence/sbom.json" in artifact_paths
    export_prefixes = tuple(
        path for paths in case.exports.values() for path in paths
    )
    content_paths = [
        path for path in artifact_paths if not path.startswith("evidence/")
    ]
    assert content_paths
    assert all(path.startswith(export_prefixes) for path in content_paths)
    assert all(
        any(path.startswith(prefix) for path in content_paths)
        for prefix in export_prefixes
    )
    assert all(item.size > 0 for item in first.artifacts)
    assert {(item.type.value, item.status.value) for item in first.evidence} == {
        ("manifest_validation", "valid"),
        ("content_hash", "valid"),
        ("sbom", "valid"),
        ("bundle_evals", "valid"),
    }
    assert not (BUNDLES_ROOT / case.relative_path / "bundle.signature.json").exists()


@pytest.mark.parametrize(
    ("relative_path", "expected_legacy_ids"),
    [
        (
            "solutions/ecommerce-operations-base",
            ["w01-order-management", "w02-product-inventory"],
        ),
        ("solutions/ecommerce-growth", ["w03-customer-private-domain"]),
    ],
)
def test_real_ecommerce_loader_exposes_only_frozen_legacy_migration_inputs(
    relative_path: str, expected_legacy_ids: list[str]
) -> None:
    loader = ManifestLoader({"m5-fixtures": BUNDLES_ROOT})

    loaded = loader.load(f"bundle://m5-fixtures/{relative_path}")

    assert [item.legacy_id for item in loaded.legacy_workshops] == expected_legacy_ids
    assert all(item.route.startswith("/workshop/") for item in loaded.legacy_workshops)
    assert all(item.widget_ids for item in loaded.legacy_workshops)
    assert all(item.required_objects for item in loaded.legacy_workshops)


EXPECTED_WORKSHOP_MODULES = (
    ("ecommerce.task-cockpit", "/workshop/cockpit", 10, "solution.ecommerce.growth"),
    (
        "ecommerce.content-campaign",
        "/workshop/content-campaign",
        20,
        "solution.ecommerce.growth",
    ),
    (
        "ecommerce.operations",
        "/workshop/operations",
        30,
        "solution.ecommerce.operations-base",
    ),
    (
        "ecommerce.creator-growth",
        "/workshop/creator-growth",
        40,
        "solution.ecommerce.growth",
    ),
    (
        "ecommerce.media-studio",
        "/workshop/media-studio",
        50,
        "solution.ecommerce.growth",
    ),
    ("ecommerce.analyst", "/workshop/analyst", 60, "solution.ecommerce.growth"),
    (
        "ecommerce.price-governance",
        "/workshop/price-governance",
        70,
        "solution.ecommerce.growth",
    ),
    ("ecommerce.customer", "/workshop/customer", 80, "solution.ecommerce.growth"),
)


def test_two_solution_packs_export_exactly_eight_workshop_module_drafts() -> None:
    loader = ManifestLoader({"m5-fixtures": BUNDLES_ROOT})
    loaded_bundles = [
        loader.load("bundle://m5-fixtures/solutions/ecommerce-operations-base"),
        loader.load("bundle://m5-fixtures/solutions/ecommerce-growth"),
    ]
    actual = sorted(
        (
            module.module_id,
            module.route,
            module.order,
            loaded.manifest.metadata.id,
        )
        for loaded in loaded_bundles
        for module in loaded.workshop_modules
    )

    assert actual == sorted(EXPECTED_WORKSHOP_MODULES)
    assert len({item[0] for item in actual}) == 8
    assert len({item[1] for item in actual}) == 8
    assert len({item[2] for item in actual}) == 8
    assert all(
        module.slot == "workshop.primary.ecommerce"
        for loaded in loaded_bundles
        for module in loaded.workshop_modules
    )
    assert all(
        module.permissions.action_types == []
        for loaded in loaded_bundles
        for module in loaded.workshop_modules
    )
    assert all(
        module.required_objects
        for loaded in loaded_bundles
        for module in loaded.workshop_modules
    )
    assert all(
        module.required_aip_features
        for loaded in loaded_bundles
        for module in loaded.workshop_modules
    )


def test_every_workshop_module_has_exact_exclusive_navigation_and_ui_claims() -> None:
    loader = ManifestLoader({"m5-fixtures": BUNDLES_ROOT})
    loaded_bundles = [
        loader.load("bundle://m5-fixtures/solutions/ecommerce-operations-base"),
        loader.load("bundle://m5-fixtures/solutions/ecommerce-growth"),
    ]

    claims = [
        claim.model_dump(mode="json", by_alias=True)
        for loaded in loaded_bundles
        for claim in loaded.manifest.spec.contributions
    ]
    assert len(claims) == 16
    for loaded in loaded_bundles:
        for module in loaded.workshop_modules:
            assert {
                "kind": "navigation",
                "route": module.route,
                "mode": "exclusive",
            } in claims
            assert {
                "kind": "ui",
                "slot": module.slot,
                "id": module.module_id,
                "mode": "exclusive",
            } in claims


def test_solution_release_evidence_names_modules_and_stays_blocked() -> None:
    loader = ManifestLoader({"m5-fixtures": BUNDLES_ROOT})
    loaded_bundles = [
        loader.load("bundle://m5-fixtures/solutions/ecommerce-operations-base"),
        loader.load("bundle://m5-fixtures/solutions/ecommerce-growth"),
    ]

    for loaded in loaded_bundles:
        bundle_path = next(
            BUNDLES_ROOT / case.relative_path
            for case in BUNDLE_CASES
            if case.bundle_id == loaded.manifest.metadata.id
        )
        evals = json.loads(
            (bundle_path / "evidence/bundle-evals.json").read_text(encoding="utf-8")
        )
        sbom = json.loads(
            (bundle_path / "evidence/sbom.json").read_text(encoding="utf-8")
        )
        component_names = {item["name"] for item in sbom["components"]}

        assert evals["status"] == "passed"
        assert evals["runtimeReadiness"] == "blocked"
        assert "active_installation_unavailable" in evals["runtimeBlockers"]
        assert {
            module.module_id for module in loaded.workshop_modules
        }.issubset(component_names)

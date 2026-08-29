"""W1-A contracts for canonical and legacy Workshop bundle assets."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from aos_api.asset_registry.contracts import WorkshopModuleContribution
from aos_api.asset_registry.errors import ManifestInvalidError
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.aip_production_profile_contracts import ProductionProfile

REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_PATH = (
    REPO_ROOT
    / "packages/contracts/schemas/asset-bundles/workshop-module-v1.schema.json"
)


def _manifest(*, contributions: list[dict] | None = None) -> dict:
    return {
        "apiVersion": "aos.dev/v1alpha1",
        "kind": "SolutionPack",
        "metadata": {
            "id": "solution.example",
            "version": "1.0.0",
            "displayName": "Example",
            "publisher": "aos",
            "license": "internal",
        },
        "spec": {
            "platformApi": ">=1.7.0 <2.0.0",
            "dependencies": [],
            "optionalDependencies": [],
            "conflicts": [],
            "exports": {"workshops": ["content/workshops/"]},
            "capabilities": {"provides": [], "requires": []},
            "permissions": {
                "roles": [],
                "markings": [],
                "dataScopes": [],
                "actionTypes": [],
            },
            "migrations": {
                "plan": None,
                "downgradePolicy": "retain-canonical",
            },
            "preflight": None,
            "regression": None,
            "rollback": None,
            "contributions": contributions or [],
        },
    }


def _canonical_module(
    *,
    module_id: str = "ecommerce.task-cockpit",
    route: str = "/workshop/cockpit",
) -> dict:
    return {
        "schema": "aos.workshop-module/v1",
        "moduleId": module_id,
        "displayName": "电商日常任务总控大屏",
        "menuLabel": "日常任务总控大屏",
        "route": route,
        "slot": "workshop.primary.ecommerce",
        "order": 10,
        "bundleRef": "bundle://aos/solution.example@1.0.0",
        "requiredObjects": ["Task", "TaskRun"],
        "requiredCapabilities": ["strategy.plan"],
        "requiredAipFeatures": ["aip.task-brief"],
        "permissions": {
            "roles": ["operator"],
            "markings": [],
            "dataScopes": ["task.read"],
            "actionTypes": [],
        },
        "viewRefs": ["content/views/cockpit.json"],
        "evalPackRefs": ["content/evals/cockpit.json"],
        "productionContractRefs": ["content/schemas/task-brief.json"],
        "responsibilityTemplateRefs": ["content/policies/responsibility.json"],
        "impactCalculatorRefs": [],
        "legacyAssetRefs": [],
        "legacyRedirects": ["/s2/task-cockpit"],
        "minimumRuntimeVersion": "1.7.0",
    }


def _claims(
    *,
    module_id: str = "ecommerce.task-cockpit",
    route: str = "/workshop/cockpit",
) -> list[dict]:
    return [
        {"kind": "navigation", "route": route, "mode": "exclusive"},
        {
            "kind": "ui",
            "slot": "workshop.primary.ecommerce",
            "id": module_id,
            "mode": "exclusive",
        },
    ]


def _make_bundle(
    root: Path,
    *,
    modules: dict[str, dict],
    contributions: list[dict] | None = None,
) -> Path:
    bundle = root / "example"
    workshop_root = bundle / "content/workshops"
    workshop_root.mkdir(parents=True, exist_ok=True)
    (bundle / "bundle.yaml").write_text(
        yaml.safe_dump(
            _manifest(contributions=contributions),
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    for relative_path in [
        "content/views/cockpit.json",
        "content/evals/cockpit.json",
        "content/schemas/task-brief.json",
        "content/policies/responsibility.json",
    ]:
        path = bundle / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
    for name, payload in modules.items():
        (workshop_root / name).write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
    return bundle


def _load(root: Path):
    return ManifestLoader({"fixtures": root}).load("bundle://fixtures/example")


def test_ecommerce_source_bundles_publish_eight_typed_non_placeholder_profiles() -> None:
    candidate_root = REPO_ROOT / "bundles/candidates/ecommerce"
    growth = ManifestLoader({"candidate": candidate_root}).load(
        "bundle://candidate/solution.ecommerce.growth/1.4.0"
    )
    operations = ManifestLoader({"candidate": candidate_root}).load(
        "bundle://candidate/solution.ecommerce.operations-base/1.2.0"
    )
    growth_exports = growth.manifest.spec.exports.model_dump()
    assert growth_exports["agents"] == [
        "content/agents/",
        "content/knowledge/",
        "content/live/",
        "content/media/",
    ]
    assert growth_exports["logic"] == ["content/logic/", "content/growth/"]
    assert growth_exports["evals"] == ["content/evals/", "content/harness/"]
    modules = [*growth.workshop_modules, *operations.workshop_modules]

    assert len(modules) == 8
    assert len({item.module_id for item in modules}) == 8
    for module in modules:
        assert len(module.eval_pack_refs) == 1
        if module.module_id == "ecommerce.media-studio":
            assert module.production_contract_refs == [
                "content/production-profiles/ecommerce.media-studio.json",
                "content/media-production-templates/lite.stage.json",
                "content/media-production-templates/standard.stage.json",
                "content/media-production-templates/full.stage.json",
            ]
            assert module.responsibility_template_refs == [
                "content/media-production-templates/lite.responsibility.json",
                "content/media-production-templates/standard.responsibility.json",
                "content/media-production-templates/full.responsibility.json",
            ]
        else:
            assert module.eval_pack_refs == module.production_contract_refs
            assert module.eval_pack_refs == module.responsibility_template_refs
        profile_path = (
            REPO_ROOT
            / "bundles/candidates/ecommerce"
            / (
                "solution.ecommerce.operations-base/1.2.0"
                if module.module_id == "ecommerce.operations"
                else "solution.ecommerce.growth/1.4.0"
            )
            / module.production_contract_refs[0]
        )
        assert "placeholder" not in profile_path.name
        assert "dry-run" not in profile_path.name
        profile = ProductionProfile.model_validate(
            json.loads(profile_path.read_text(encoding="utf-8"))
        )
        assert profile.module_id == module.module_id
        assert profile.contribution_projection.show_atomic_skill_attribution is True
        assert profile.contribution_projection.show_logic_revision is True
        assert profile.contribution_projection.show_coworker_binding is True

    schema_root = (
        REPO_ROOT
        / "bundles/candidates/ecommerce/domain.ecommerce.core/1.1.0/content/schemas"
    )
    schema_ids = {
        json.loads(path.read_text(encoding="utf-8"))["$id"]
        for path in schema_root.glob("ecommerce-*.v1.schema.json")
    }
    assert schema_ids == {
        "aos.ecommerce-production-profile/v1",
        "aos.ecommerce-brief-spec/v1",
        "aos.ecommerce-evidence-selection/v1",
        "aos.ecommerce-eval-profile/v1",
        "aos.ecommerce-responsibility-template/v1",
    }

    historical_growth = json.loads(
        (
            REPO_ROOT
            / "bundles/solutions/ecommerce-growth/content/workshops/ecommerce.task-cockpit.json"
        ).read_text(encoding="utf-8")
    )
    assert historical_growth["bundleRef"].endswith("@1.3.0")
    assert historical_growth["productionContractRefs"] == []

    for historical, candidate in (
        (
            REPO_ROOT / "bundles/domains/ecommerce-core",
            candidate_root / "domain.ecommerce.core/1.1.0",
        ),
        (
            REPO_ROOT / "bundles/solutions/ecommerce-growth",
            candidate_root / "solution.ecommerce.growth/1.4.0",
        ),
        (
            REPO_ROOT / "bundles/solutions/ecommerce-operations-base",
            candidate_root / "solution.ecommerce.operations-base/1.2.0",
        ),
    ):
        historical_paths = {
            path.relative_to(historical).as_posix()
            for path in historical.rglob("*")
            if path.is_file()
        }
        candidate_paths = {
            path.relative_to(candidate).as_posix()
            for path in candidate.rglob("*")
            if path.is_file()
        }
        assert historical_paths <= candidate_paths


def test_canonical_module_contract_is_strict_and_schema_is_in_sync() -> None:
    module = WorkshopModuleContribution.model_validate(_canonical_module())
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert module.module_id == "ecommerce.task-cockpit"
    assert module.route == "/workshop/cockpit"
    assert schema == WorkshopModuleContribution.model_json_schema(by_alias=True)

    invalid = _canonical_module()
    invalid["unknown"] = True
    with pytest.raises(ValidationError):
        WorkshopModuleContribution.model_validate(invalid)


def test_loader_parses_canonical_module_and_binds_claims_and_artifacts(
    tmp_path: Path,
) -> None:
    root = tmp_path / "allowed"
    _make_bundle(
        root,
        modules={"ecommerce.task-cockpit.json": _canonical_module()},
        contributions=_claims(),
    )

    loaded = _load(root)

    assert [item.module_id for item in loaded.workshop_modules] == [
        "ecommerce.task-cockpit"
    ]
    assert loaded.legacy_workshops == []


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.update(bundleRef="bundle://aos/wrong@1.0.0"),
        lambda payload: payload.update(viewRefs=["content/views/missing.json"]),
        lambda payload: payload.update(route="/workshop/not-claimed"),
        lambda payload: payload.update(moduleId="ecommerce.not-claimed"),
    ],
)
def test_loader_rejects_unbound_or_missing_canonical_references(
    tmp_path: Path, mutate
) -> None:
    root = tmp_path / "allowed"
    module = _canonical_module()
    mutate(module)
    _make_bundle(
        root,
        modules={"module.json": module},
        contributions=_claims(),
    )

    with pytest.raises(ManifestInvalidError):
        _load(root)


@pytest.mark.parametrize("duplicate_field", ["moduleId", "route"])
def test_loader_rejects_duplicate_canonical_identity_or_route(
    tmp_path: Path, duplicate_field: str
) -> None:
    root = tmp_path / "allowed"
    first = _canonical_module()
    second = _canonical_module(
        module_id="ecommerce.content-campaign",
        route="/workshop/content-campaign",
    )
    second[duplicate_field] = first[duplicate_field]
    contributions = [
        *_claims(),
        *_claims(
            module_id="ecommerce.content-campaign",
            route="/workshop/content-campaign",
        ),
    ]
    _make_bundle(
        root,
        modules={"first.json": first, "second.json": second},
        contributions=contributions,
    )

    with pytest.raises(ManifestInvalidError):
        _load(root)


def test_loader_adapts_only_frozen_legacy_workshop_shape(tmp_path: Path) -> None:
    root = tmp_path / "allowed"
    legacy = {
        "workshop_id": "w01-order-management",
        "title": "订单与履约运营台",
        "route": "workshop/orders",
        "widgets": [
            {"id": "order-funnel", "title": "状态漏斗", "source_ot": "Order"}
        ],
        "decision_tags": "BLOCKED_PENDING_G2",
    }
    _make_bundle(root, modules={"w01-order-management.json": legacy})

    loaded = _load(root)

    assert loaded.workshop_modules == []
    assert [item.model_dump(by_alias=True) for item in loaded.legacy_workshops] == [
        {
            "sourcePath": "content/workshops/w01-order-management.json",
            "legacyId": "w01-order-management",
            "title": "订单与履约运营台",
            "route": "/workshop/orders",
            "widgetIds": ["order-funnel"],
            "requiredObjects": ["Order"],
        }
    ]

    legacy["unexpected"] = "not allowed"
    _make_bundle(root, modules={"w01-order-management.json": legacy})
    with pytest.raises(ManifestInvalidError):
        _load(root)


def test_loader_rejects_unknown_unschematized_workshop(tmp_path: Path) -> None:
    root = tmp_path / "allowed"
    _make_bundle(root, modules={"unknown.json": {"title": "ambiguous"}})

    with pytest.raises(ManifestInvalidError):
        _load(root)


def test_loader_recognizes_strict_analyst_auxiliary_asset_without_projection(
    tmp_path: Path,
) -> None:
    root = tmp_path / "allowed"
    analyst_asset = {
        "schemaVersion": 1,
        "bundleRef": "bundle://aos/solution.example@1.0.0",
        "templates": [
            {
                "templateId": "ecommerce.analyst.data-advisor.orders",
                "revision": 1,
                "roleId": "ecommerce.data-advisor",
                "roleName": "数据参谋",
                "queryKind": "semantic",
                "defaultObjectType": "Order",
                "defaultPrompt": "",
                "requiredObjectTypes": ["Order"],
                "requiredLogicIds": ["D01"],
                "sourceDataTypes": ["order"],
                "purpose": "读取真实订单事实",
                "policy": "canonical-read-only",
            }
        ],
    }
    _make_bundle(root, modules={"analyst-templates.json": analyst_asset})

    loaded = _load(root)

    assert loaded.workshop_modules == []
    assert loaded.legacy_workshops == []


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.update(
            bundleRef="bundle://aos/solution.wrong@1.0.0"
        ),
        lambda payload: payload.update(unexpected=True),
        lambda payload: payload["templates"][0].update(policy="write-enabled"),
        lambda payload: payload["templates"][0].update(requiredObjectTypes=[]),
    ],
)
def test_loader_rejects_drifted_analyst_auxiliary_asset(
    tmp_path: Path, mutate
) -> None:
    root = tmp_path / "allowed"
    analyst_asset = {
        "schemaVersion": 1,
        "bundleRef": "bundle://aos/solution.example@1.0.0",
        "templates": [
            {
                "templateId": "ecommerce.analyst.data-advisor.orders",
                "revision": 1,
                "roleId": "ecommerce.data-advisor",
                "roleName": "数据参谋",
                "queryKind": "semantic",
                "defaultObjectType": "Order",
                "defaultPrompt": "",
                "requiredObjectTypes": ["Order"],
                "requiredLogicIds": ["D01"],
                "sourceDataTypes": ["order"],
                "purpose": "读取真实订单事实",
                "policy": "canonical-read-only",
            }
        ],
    }
    mutate(analyst_asset)
    _make_bundle(root, modules={"analyst-templates.json": analyst_asset})

    with pytest.raises(ManifestInvalidError):
        _load(root)

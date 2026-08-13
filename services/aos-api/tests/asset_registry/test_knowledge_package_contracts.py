"""E6A contracts for fail-closed VerticalPack knowledge exports."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aos_api.asset_registry import (
    KNOWLEDGE_PACKAGE_API_VERSION,
    BundleManifest,
    KnowledgePackageManifest,
    parse_knowledge_package_json,
)

NOW = datetime(2026, 8, 13, 16, 0, tzinfo=UTC)
HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64
SCHEMA_PATH = (
    Path(__file__).resolve().parents[4]
    / "packages/contracts/schemas/asset-bundles/knowledge-package-v1alpha1.schema.json"
)


def _package() -> dict:
    return {
        "apiVersion": KNOWLEDGE_PACKAGE_API_VERSION,
        "kind": "KnowledgePackage",
        "packageId": "vertical.ecommerce.beauty",
        "packageVersion": "1.0.0",
        "sourceInventory": [
            {
                "sourceId": "nmpa.inventory",
                "sourceUri": "https://www.nmpa.gov.cn/example/list-i",
                "observedAt": NOW.isoformat(),
                "freshnessExpiresAt": (NOW + timedelta(days=30)).isoformat(),
                "licenseId": "official-source-review-pending",
                "usagePolicy": "citation-only-until-reviewed",
                "licenseDecision": "unknown",
                "contentHash": HASH_A,
                "provider": "nmpa",
                "providerVersion": "list-i-2026-08-13",
            }
        ],
        "entries": [
            {
                "entryId": "ingredient.example",
                "category": "ingredient",
                "payloadPath": "content/knowledge/entries/ingredient.example.json",
                "payloadHash": HASH_B,
                "sourceId": "nmpa.inventory",
                "markings": ["public"],
                "applicability": ["vertical.ecommerce.beauty"],
                "ownerRoles": ["shopping_advisor", "content_officer"],
            }
        ],
        "rollback": {
            "mode": "remove-projection-retain-canonical",
            "receiptRequired": True,
        },
    }


def _parse(payload: dict) -> KnowledgePackageManifest:
    return parse_knowledge_package_json(json.dumps(payload, ensure_ascii=False))


def test_vertical_pack_can_export_versioned_knowledge_paths() -> None:
    manifest = BundleManifest.model_validate(
        {
            "apiVersion": "aos.dev/v1alpha1",
            "kind": "VerticalPack",
            "metadata": {
                "id": "vertical.ecommerce.beauty",
                "version": "1.0.0",
                "displayName": "Beauty Knowledge",
                "publisher": "aos",
                "license": "internal",
            },
            "spec": {
                "platformApi": ">=1.7.0 <2.0.0",
                "dependencies": [],
                "optionalDependencies": [],
                "conflicts": [],
                "exports": {"knowledge": ["content/knowledge/"]},
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
            },
        }
    )
    assert manifest.spec.exports.knowledge == ["content/knowledge/"]


def test_non_vertical_bundle_cannot_export_knowledge() -> None:
    payload = {
        "apiVersion": "aos.dev/v1alpha1",
        "kind": "SolutionPack",
        "metadata": {
            "id": "solution.invalid-knowledge",
            "version": "1.0.0",
            "displayName": "Invalid",
            "publisher": "aos",
            "license": "internal",
        },
        "spec": {
            "platformApi": ">=1.7.0 <2.0.0",
            "dependencies": [],
            "optionalDependencies": [],
            "conflicts": [],
            "exports": {"knowledge": ["content/knowledge/"]},
            "capabilities": {"provides": [], "requires": []},
            "permissions": {
                "roles": [], "markings": [], "dataScopes": [], "actionTypes": []
            },
            "migrations": {"plan": None, "downgradePolicy": "retain-canonical"},
            "preflight": None,
            "regression": None,
            "rollback": None,
        },
    }
    with pytest.raises(ValidationError, match="restricted to VerticalPack"):
        BundleManifest.model_validate(payload)


def test_knowledge_manifest_round_trips_and_blocks_unknown_license() -> None:
    package = _parse(_package())

    dumped = package.model_dump(mode="json", by_alias=True)
    assert _parse(dumped) == package
    assert dumped["sourceInventory"][0]["observedAt"] == "2026-08-13T16:00:00Z"
    assert package.readiness_blockers(now=NOW) == ("license_unknown:nmpa.inventory",)


def test_allowed_fresh_source_is_ready_without_mutating_authority() -> None:
    payload = _package()
    payload["sourceInventory"][0]["licenseDecision"] = "allowed"
    package = _parse(payload)

    assert package.readiness_blockers(now=NOW) == ()
    assert package.source_inventory[0].license_decision.value == "allowed"


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("../escape.json", "must not traverse"),
        ("/absolute.json", "relative path"),
        ("content\\knowledge\\entry.json", "relative path"),
        ("https://evil.example/entry.json", "relative path"),
    ],
)
def test_knowledge_payload_paths_fail_closed(path: str, message: str) -> None:
    payload = _package()
    payload["entries"][0]["payloadPath"] = path
    with pytest.raises(ValidationError, match=message):
        _parse(payload)


@pytest.mark.parametrize(
    "source_uri",
    [
        "file:///tmp/source.json",
        "http://example.com/source",
        "https://user:password@example.com/source",
        "https://example.com/source#secret",
        "relative/source",
    ],
)
def test_source_uri_rejects_local_credentials_fragments_and_relative_forms(
    source_uri: str,
) -> None:
    payload = _package()
    payload["sourceInventory"][0]["sourceUri"] = source_uri
    with pytest.raises(ValidationError):
        _parse(payload)


def test_entry_requires_inventoried_source_and_unique_payload_path() -> None:
    missing = _package()
    missing["entries"][0]["sourceId"] = "unknown.source"
    with pytest.raises(ValidationError, match="inventoried source"):
        _parse(missing)

    duplicate = _package()
    second = deepcopy(duplicate["entries"][0])
    second["entryId"] = "ingredient.second"
    duplicate["entries"].append(second)
    with pytest.raises(ValidationError, match="payload paths must be unique"):
        _parse(duplicate)


def test_hash_freshness_unknown_fields_and_rollback_are_strict() -> None:
    invalid_hash = _package()
    invalid_hash["entries"][0]["payloadHash"] = "a" * 64
    with pytest.raises(ValidationError):
        _parse(invalid_hash)

    stale_window = _package()
    stale_window["sourceInventory"][0]["freshnessExpiresAt"] = NOW.isoformat()
    with pytest.raises(ValidationError, match="must follow"):
        _parse(stale_window)

    unknown = _package()
    unknown["sourceInventory"][0]["authorized"] = True
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _parse(unknown)

    rollback = _package()
    rollback["rollback"]["receiptRequired"] = False
    with pytest.raises(ValidationError):
        _parse(rollback)


def test_stale_and_denied_sources_report_stable_blockers() -> None:
    payload = _package()
    payload["sourceInventory"][0]["licenseDecision"] = "denied"
    package = _parse(payload)

    assert package.readiness_blockers(now=NOW + timedelta(days=31)) == (
        "license_denied:nmpa.inventory",
        "source_stale:nmpa.inventory",
    )


def test_serialized_loader_rejects_duplicate_keys_and_non_object_roots() -> None:
    with pytest.raises(ValueError, match="duplicate key"):
        parse_knowledge_package_json('{"apiVersion":"one","apiVersion":"two"}')
    with pytest.raises(ValueError, match="root must be an object"):
        parse_knowledge_package_json("[]")


def test_shared_knowledge_schema_tracks_strict_dto_surface() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    generated = KnowledgePackageManifest.model_json_schema(by_alias=True)

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(generated["required"])
    assert set(schema["properties"]) == set(generated["properties"])
    assert schema["$defs"]["source"]["additionalProperties"] is False
    assert schema["$defs"]["entry"]["additionalProperties"] is False
    assert schema["$defs"]["rollback"]["additionalProperties"] is False

"""Cross-group checks for the frozen M5 ecommerce skeleton composition."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.composition_contracts import (
    CompositionRequest,
    CreateInstallationRequest,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
BUNDLE_ROOT = REPO_ROOT / "bundles"
OVERLAY_FIXTURE = (
    REPO_ROOT
    / "services/aos-api/tests/asset_registry/fixtures/m5/instance-overlay.synthetic.json"
)

EXPECTED_OVERLAY_REVISION = (
    "sha256:5c1d43e9d41081e43ed25b5e3790abefbe23f2ae7b60dff35397d788be7056e7"
)
CORE_COORDINATE = "domain.ecommerce.core"
LEAF_COORDINATES = {
    "platform.ecommerce.niushop",
    "solution.ecommerce.growth",
    "solution.ecommerce.operations-base",
}
MANIFEST_PATHS = (
    BUNDLE_ROOT / "domains/ecommerce-core/bundle.yaml",
    BUNDLE_ROOT / "platforms/ecommerce-niushop/bundle.yaml",
    BUNDLE_ROOT / "solutions/ecommerce-growth/bundle.yaml",
    BUNDLE_ROOT / "solutions/ecommerce-operations-base/bundle.yaml",
)


def _load_manifest(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_three_leaf_request_matches_the_four_bundle_dependency_graph() -> None:
    manifests = [_load_manifest(path) for path in MANIFEST_PATHS]
    by_id = {manifest["metadata"]["id"]: manifest for manifest in manifests}

    assert set(by_id) == LEAF_COORDINATES | {CORE_COORDINATE}
    assert by_id[CORE_COORDINATE]["spec"]["dependencies"] == []
    for coordinate in LEAF_COORDINATES:
        dependencies = by_id[coordinate]["spec"]["dependencies"]
        assert dependencies == [
            {
                "publisher": "aos",
                "id": CORE_COORDINATE,
                "version": ">=1.0.0 <2.0.0",
            }
        ]

    request = CompositionRequest.model_validate(
        {
            "requested": [
                {"publisher": "aos", "id": coordinate, "version": "1.0.0"}
                for coordinate in sorted(LEAF_COORDINATES, reverse=True)
            ],
            "platformApiVersion": "1.7.0",
            "platformRelease": "aos-platform/1.7.0",
            "environment": "dev",
        }
    )
    assert [item.id for item in request.requested] == sorted(LEAF_COORDINATES)
    assert CORE_COORDINATE not in {item.id for item in request.requested}


def test_overlay_canonical_hash_flows_through_existing_installation_contract() -> None:
    overlay = json.loads(OVERLAY_FIXTURE.read_text(encoding="utf-8"))
    overlay_revision = canonical_sha256(overlay)

    assert overlay_revision == EXPECTED_OVERLAY_REVISION
    assert overlay["approvals"]["overlayRevisionRef"] == overlay["metadata"]["revision"]

    request = CreateInstallationRequest.model_validate(
        {
            "compositionId": overlay["compositionLockRef"]["compositionId"],
            "lockRevision": overlay["compositionLockRef"]["revision"],
            "overlayRevision": overlay_revision,
            "displayName": "Synthetic M5 ecommerce composition",
        }
    )
    assert request.overlay_revision == overlay_revision
    assert request.composition_id == overlay["compositionLockRef"]["compositionId"]
    assert request.lock_revision == overlay["compositionLockRef"]["revision"]

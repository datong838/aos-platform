"""BI-W9-07 cross-fixture regression seal for three disabled AdapterPacks."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path

import pytest

from aos_api.business_investigation_adapter_activation import (
    AdapterActivationMatrix,
    evaluate_activation_matrix,
)
from aos_api.business_investigation_adapter_capability import (
    AdapterCapabilityMatrix,
    evaluate_adapter_capability_matrix,
)
from aos_api.business_investigation_connector_contract import (
    ConnectorFailureFixtureMatrix,
    evaluate_connector_fixture_matrix,
)
from aos_api.business_investigation_douyin_store_profile import (
    DouyinStoreProfile,
    evaluate_douyin_store_profile,
)
from aos_api.business_investigation_instance_overlay import (
    BusinessInvestigationInstanceOverlay,
    evaluate_instance_overlay,
)
from aos_api.business_investigation_niushop_profile import (
    NiushopProfile,
    evaluate_niushop_profile,
)
from aos_api.business_investigation_wechat_store_profile import (
    WechatStoreProfile,
    evaluate_wechat_store_profile,
)


FIXTURE_ROOT = Path(__file__).parent / "fixtures/business_investigation"
MANIFEST_PATH = FIXTURE_ROOT / "adapter_pack_regression_manifest.json"
PLATFORMS = {"niushop", "wechat_store", "douyin_store"}
ALLOWED_SOURCE_KINDS = {"synthetic", "historical_redacted"}
EXPECTED_FILES = {
    "adapter_capability_matrix.json",
    "niushop_profile.json",
    "wechat_store_profile.json",
    "douyin_store_profile.json",
    "instance_overlay.json",
    "adapter_activation_matrix.json",
    "connector_failure_matrix.json",
}
FORBIDDEN_KEYS = {"password", "credential", "accessToken", "refreshToken", "cookie", "locator"}
NOW = datetime.fromisoformat("2026-08-27T00:00:00+00:00")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _walk_forbidden(value: object, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_KEYS:
                raise ValueError(f"forbidden sensitive or locator field at {path}.{key}")
            _walk_forbidden(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_forbidden(child, f"{path}[{index}]")


def _validate_manifest(manifest: dict) -> dict[str, dict]:
    if manifest.get("schemaVersion") != "aos.business-investigation.adapter-pack-regression-manifest/v1":
        raise ValueError("unsupported regression manifest schema")
    if manifest.get("noExternalEffect") is not True:
        raise ValueError("regression manifest must guarantee no external effect")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != len(EXPECTED_FILES):
        raise ValueError("regression manifest must list all seven fixtures")
    _walk_forbidden(manifest)

    by_file: dict[str, dict] = {}
    for artifact in artifacts:
        filename = artifact.get("path")
        if not isinstance(filename, str) or Path(filename).name != filename:
            raise ValueError("fixture path must be a local basename")
        if filename in by_file:
            raise ValueError("fixture paths must be unique")
        if not set(artifact.get("sourceKinds", [])) <= ALLOWED_SOURCE_KINDS:
            raise ValueError("fixture sourceKind must be synthetic or historical_redacted")
        platforms = set(artifact.get("platforms", []))
        if not platforms or not platforms <= PLATFORMS:
            raise ValueError("fixture platform coverage is invalid")
        fixture_path = FIXTURE_ROOT / filename
        payload = _load(fixture_path)
        if artifact.get("sha256") != _sha256(fixture_path):
            raise ValueError(f"fixture hash drifted: {filename}")
        if artifact.get("schemaVersion") != payload.get("schemaVersion"):
            raise ValueError(f"fixture schema drifted: {filename}")
        if payload.get("platform") is not None and payload["platform"] not in platforms:
            raise ValueError(f"fixture platform drifted: {filename}")
        by_file[filename] = payload

    if set(by_file) != EXPECTED_FILES:
        raise ValueError("regression manifest fixture set drifted")
    return by_file


def test_manifest_seals_all_three_platform_fixtures_without_external_effect() -> None:
    fixtures = _validate_manifest(_load(MANIFEST_PATH))

    capability = AdapterCapabilityMatrix.model_validate(fixtures["adapter_capability_matrix.json"])
    assert capability.content_hash == capability.calculated_hash()
    assert set(evaluate_adapter_capability_matrix(capability).platforms) == PLATFORMS

    profiles = (
        (NiushopProfile, evaluate_niushop_profile, "niushop_profile.json", "niushop"),
        (WechatStoreProfile, evaluate_wechat_store_profile, "wechat_store_profile.json", "wechat_store"),
        (DouyinStoreProfile, evaluate_douyin_store_profile, "douyin_store_profile.json", "douyin_store"),
    )
    for model, evaluate, filename, platform in profiles:
        profile = model.model_validate(fixtures[filename])
        assert profile.content_hash == profile.calculated_hash()
        receipt = evaluate(profile)
        assert profile.platform == platform
        assert receipt.status == "passed"

    overlay = BusinessInvestigationInstanceOverlay.model_validate(fixtures["instance_overlay.json"])
    assert overlay.content_hash == overlay.calculated_hash()
    assert evaluate_instance_overlay(overlay).status == "passed"

    activation = AdapterActivationMatrix.model_validate(fixtures["adapter_activation_matrix.json"])
    assert activation.content_hash == activation.calculated_hash()
    decisions = evaluate_activation_matrix(activation, "org-org", "dev-project", NOW)
    assert set(decisions) == PLATFORMS
    assert all(not item.activation_executed and not item.external_effect for item in decisions.values())

    failures = ConnectorFailureFixtureMatrix.model_validate(fixtures["connector_failure_matrix.json"])
    assert failures.content_hash == failures.calculated_hash()
    failure_receipt = evaluate_connector_fixture_matrix(failures)
    assert set(failure_receipt.platforms) == PLATFORMS
    assert failure_receipt.status == "passed"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("path", "../niushop_profile.json", "local basename"),
        ("sha256", "sha256:" + "0" * 64, "hash drifted"),
        ("schemaVersion", "aos.invalid/v1", "schema drifted"),
        ("sourceKinds", ["live"], "sourceKind"),
        ("platforms", ["wechat_store"], "platform drifted"),
    ],
)
def test_manifest_rejects_path_hash_schema_source_and_platform_drift(field: str, value: object, message: str) -> None:
    manifest = _load(MANIFEST_PATH)
    target = next(item for item in manifest["artifacts"] if item["path"] == "niushop_profile.json")
    target[field] = value
    with pytest.raises(ValueError, match=message):
        _validate_manifest(manifest)


def test_manifest_rejects_sensitive_or_locator_payload() -> None:
    manifest = _load(MANIFEST_PATH)
    manifest["credential"] = "must-not-enter-fixtures"
    with pytest.raises(ValueError, match="forbidden sensitive or locator"):
        _validate_manifest(manifest)


def test_one_platform_manifest_drift_does_not_change_other_platform_entries() -> None:
    manifest = _load(MANIFEST_PATH)
    before = {item["path"]: deepcopy(item) for item in manifest["artifacts"]}
    target = next(item for item in manifest["artifacts"] if item["path"] == "wechat_store_profile.json")
    target["sha256"] = "sha256:" + "f" * 64
    after = {item["path"]: item for item in manifest["artifacts"]}

    unchanged = EXPECTED_FILES - {"wechat_store_profile.json"}
    assert all(after[name] == before[name] for name in unchanged)
    with pytest.raises(ValueError, match="wechat_store_profile.json"):
        _validate_manifest(manifest)

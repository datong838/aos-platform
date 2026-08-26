"""BI-W9-04 disabled Douyin Store page/export Profile tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aos_api.business_investigation_douyin_store_profile import (
    DOUYIN_STORE_EXPORT_FAMILIES,
    DOUYIN_STORE_SEMANTIC_FAMILIES,
    DouyinStoreProfile,
    evaluate_douyin_page_observation,
    evaluate_douyin_store_profile,
)


FIXTURE = Path(__file__).parent / "fixtures/business_investigation/douyin_store_profile.json"
HASH_B = f"sha256:{'b' * 64}"


def fixture_payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_profile_covers_required_page_and_export_semantics_without_access_claim() -> None:
    profile = DouyinStoreProfile.model_validate(fixture_payload())
    receipt = evaluate_douyin_store_profile(profile)
    page_families = {family for item in profile.page_semantics for family in item.fact_families}
    export_families = {family for item in profile.export_mappings for family in item.fact_families}
    assert DOUYIN_STORE_SEMANTIC_FAMILIES <= page_families
    assert DOUYIN_STORE_EXPORT_FAMILIES <= export_families
    assert all(item.calculated_signature_hash() == item.signature_hash for item in profile.page_semantics)
    assert all(item.requires_observation for item in profile.page_semantics)
    assert all(item.requires_permission and not item.permission_verified for item in profile.export_mappings)
    assert all(not item.export_allowed for item in profile.export_mappings)
    assert not profile.enabled and not profile.source_access_authorized
    assert receipt.status == "passed" and "NO_PLATFORM_ACCESS" in receipt.non_claims


def test_page_signature_match_is_usable_only_for_the_declared_semantic_contract() -> None:
    profile = DouyinStoreProfile.model_validate(fixture_payload())
    page = profile.page_semantics[0]
    result = evaluate_douyin_page_observation(profile, page.semantic_id, set(page.semantic_landmarks))
    assert result.status == "MATCHED"
    assert result.semantic_contract_usable
    assert not result.profile_activation_allowed
    assert result.missing_landmarks == []
    assert not result.automatic_retry and not result.external_effect


def test_missing_landmark_detects_page_drift_and_disables_profile_use() -> None:
    profile = DouyinStoreProfile.model_validate(fixture_payload())
    page = profile.page_semantics[0]
    result = evaluate_douyin_page_observation(profile, page.semantic_id, set(page.semantic_landmarks[1:]))
    assert result.status == "BLOCKED_PAGE_DRIFT"
    assert not result.semantic_contract_usable
    assert not result.profile_activation_allowed
    assert result.missing_landmarks == [page.semantic_landmarks[0]]
    assert result.disable_reason == "SEMANTIC_LANDMARK_MISSING"
    assert not result.automatic_retry and not result.external_effect


def test_unknown_semantic_id_and_signature_hash_drift_fail_closed() -> None:
    profile = DouyinStoreProfile.model_validate(fixture_payload())
    with pytest.raises(ValueError, match="unknown page semantic"):
        evaluate_douyin_page_observation(profile, "unknown-page", set())

    drifted = fixture_payload()
    drifted["pageSemantics"][0]["signatureHash"] = HASH_B
    with pytest.raises(ValueError, match="page signature hash drifted"):
        DouyinStoreProfile.model_validate(drifted)


def test_profile_hash_permission_and_disabled_integrity_fail_closed() -> None:
    hash_drift = fixture_payload()
    hash_drift["contentHash"] = HASH_B
    with pytest.raises(ValueError, match="profile content hash drifted"):
        evaluate_douyin_store_profile(DouyinStoreProfile.model_validate(hash_drift))

    for field in ("enabled", "sourceAccessAuthorized"):
        payload = fixture_payload()
        payload[field] = True
        with pytest.raises(ValidationError):
            DouyinStoreProfile.model_validate(payload)

    for field in ("permissionVerified", "exportAllowed"):
        payload = fixture_payload()
        payload["exportMappings"][0][field] = True
        with pytest.raises(ValidationError):
            DouyinStoreProfile.model_validate(payload)


@pytest.mark.parametrize(
    "extra",
    [
        {"url": "https://example.invalid"}, {"route": "/shop/order"}, {"selector": "#orders"},
        {"menuLabel": "真实菜单"}, {"secretRef": "secret"}, {"account": "admin"},
        {"token": "secret"}, {"cookie": "secret"}, {"rawSample": {}}, {"storeName": "real-store"},
    ],
)
def test_profile_rejects_locators_credentials_real_instance_and_raw_samples(extra: dict) -> None:
    payload = fixture_payload()
    payload.update(extra)
    with pytest.raises(ValidationError, match="Extra inputs"):
        DouyinStoreProfile.model_validate(payload)


def test_platform_page_and_export_contract_cannot_drift() -> None:
    platform = fixture_payload()
    platform["platform"] = "wechat_store"
    with pytest.raises(ValidationError):
        DouyinStoreProfile.model_validate(platform)

    missing_page = fixture_payload()
    missing_page["pageSemantics"] = missing_page["pageSemantics"][:-1]
    with pytest.raises(ValidationError, match="page semantic families"):
        DouyinStoreProfile.model_validate(missing_page)

    missing_export = fixture_payload()
    missing_export["exportMappings"] = missing_export["exportMappings"][:-1]
    with pytest.raises(ValidationError, match="export families"):
        DouyinStoreProfile.model_validate(missing_export)

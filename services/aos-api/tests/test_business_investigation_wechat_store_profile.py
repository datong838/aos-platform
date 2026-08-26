"""BI-W9-03 disabled WeChat Store page/export Profile tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aos_api.business_investigation_wechat_store_profile import (
    WECHAT_STORE_EXPORT_FAMILIES,
    WECHAT_STORE_SEMANTIC_FAMILIES,
    WechatStoreProfile,
    evaluate_wechat_store_profile,
)


FIXTURE = Path(__file__).parent / "fixtures/business_investigation/wechat_store_profile.json"
HASH_B = f"sha256:{'b' * 64}"


def fixture_payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_profile_covers_required_page_and_export_semantics_without_access_claim() -> None:
    profile = WechatStoreProfile.model_validate(fixture_payload())
    receipt = evaluate_wechat_store_profile(profile)

    page_families = {family for item in profile.page_semantics for family in item.fact_families}
    export_families = {family for item in profile.export_mappings for family in item.fact_families}
    assert WECHAT_STORE_SEMANTIC_FAMILIES <= page_families
    assert WECHAT_STORE_EXPORT_FAMILIES <= export_families
    assert all(item.requires_observation for item in profile.page_semantics)
    assert all(item.requires_permission and not item.permission_verified for item in profile.export_mappings)
    assert all(not item.export_allowed for item in profile.export_mappings)
    assert all(item.coverage_verification_required for item in profile.export_mappings)
    assert all(item.freshness_verification_required for item in profile.export_mappings)
    assert not profile.enabled and not profile.source_access_authorized
    assert profile.installation_ref is None and profile.instance_overlay_ref is None
    assert receipt.status == "passed" and "NO_PLATFORM_ACCESS" in receipt.non_claims


def test_failure_policy_keeps_permission_loading_pagination_masking_and_drift_distinct() -> None:
    policy = WechatStoreProfile.model_validate(fixture_payload()).failure_policy
    assert policy.permission_insufficient == "BLOCKED_PERMISSION"
    assert policy.async_loading_timeout == "PARTIAL_LOADING_TIMEOUT"
    assert policy.virtual_list_truncated == "PARTIAL_PAGINATION"
    assert policy.masked_value == "BLOCKED_MASKED_VALUE"
    assert policy.page_drift == "BLOCKED_PAGE_DRIFT"
    assert policy.external_unknown == "UNKNOWN_RECONCILE"
    assert not policy.automatic_retry
    assert not policy.empty_observed
    assert not policy.external_effect


def test_profile_hash_and_permission_integrity_fail_closed() -> None:
    hash_drift = fixture_payload()
    hash_drift["contentHash"] = HASH_B
    with pytest.raises(ValueError, match="profile content hash drifted"):
        evaluate_wechat_store_profile(WechatStoreProfile.model_validate(hash_drift))

    for field in ("enabled", "sourceAccessAuthorized"):
        payload = fixture_payload()
        payload[field] = True
        with pytest.raises(ValidationError):
            WechatStoreProfile.model_validate(payload)

    for field in ("permissionVerified", "exportAllowed"):
        payload = fixture_payload()
        payload["exportMappings"][0][field] = True
        with pytest.raises(ValidationError):
            WechatStoreProfile.model_validate(payload)


@pytest.mark.parametrize(
    "extra",
    [
        {"url": "https://example.invalid"},
        {"route": "/shop/order"},
        {"selector": "#orders"},
        {"menuLabel": "真实菜单"},
        {"secretRef": "secret"},
        {"account": "admin"},
        {"token": "secret"},
        {"cookie": "secret"},
        {"rawSample": {}},
    ],
)
def test_profile_rejects_runtime_locators_credentials_and_raw_samples(extra: dict) -> None:
    payload = fixture_payload()
    payload.update(extra)
    with pytest.raises(ValidationError, match="Extra inputs"):
        WechatStoreProfile.model_validate(payload)


def test_platform_page_export_and_failure_contract_cannot_drift() -> None:
    platform = fixture_payload()
    platform["platform"] = "douyin_store"
    with pytest.raises(ValidationError):
        WechatStoreProfile.model_validate(platform)

    missing_page = fixture_payload()
    missing_page["pageSemantics"] = missing_page["pageSemantics"][:-1]
    with pytest.raises(ValidationError, match="page semantic families"):
        WechatStoreProfile.model_validate(missing_page)

    missing_export = fixture_payload()
    missing_export["exportMappings"] = missing_export["exportMappings"][:-1]
    with pytest.raises(ValidationError, match="export families"):
        WechatStoreProfile.model_validate(missing_export)

    success = fixture_payload()
    success["failurePolicy"]["permissionInsufficient"] = "SUCCESS"
    with pytest.raises(ValidationError):
        WechatStoreProfile.model_validate(success)

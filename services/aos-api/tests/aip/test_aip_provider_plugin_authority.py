from __future__ import annotations

import json
from pathlib import Path

import pytest

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_provider_plugin_authority import (
    ProviderPluginAuthority,
    ProviderPluginAuthorityError,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
CANARY = TenantScope("dev-org", "dev-project")


def manifest() -> dict:
    return {
        "id": "agnes-text",
        "name": "Agnes Text",
        "nameZh": "Agnes Text（内网）",
        "description": "平台内网文本推理",
        "tier": "high",
        "modalities": ["text"],
        "capabilities": ["llm", "chat"],
        "formFamily": "openai_compatible",
        "defaultModels": ["agnes-2.0-flash"],
        "litellmPrefix": "openai/",
        "version": "0.1.0",
        "author": "aos",
        "configSchema": {"type": "object", "properties": {}},
    }


def approval() -> dict:
    return {
        "schema": "aos-provider-plugin-approval/v1",
        "providerPluginId": "agnes-text",
        "revision": 1,
        "manifestVersion": "0.1.0",
        "owner": "AOS/FDE",
        "usageBasis": "internal development pilot only",
        "approvedCapabilities": ["llm", "chat"],
        "deniedCapabilities": ["image", "audio", "video", "tool-execution"],
        "allowedTenants": [{"orgId": "org-org", "projectId": "dev-project"}],
        "approvalStatus": "approved_for_dev",
        "approvedBy": "owner",
        "approvedAt": "2026-08-16T00:00:00+08:00",
    }


def authority(tmp_path: Path, *, manifest_data: dict | None = None, approval_data: dict | None = None):
    root = tmp_path / "plugins" / "llm-providers"
    target = root / "agnes-text"
    target.mkdir(parents=True)
    (target / "manifest.json").write_text(
        json.dumps(manifest_data or manifest(), ensure_ascii=False), encoding="utf-8"
    )
    if approval_data is not None:
        (target / "approval.json").write_text(
            json.dumps(approval_data, ensure_ascii=False), encoding="utf-8"
        )
    return ProviderPluginAuthority(root=root)


def test_approved_manifest_builds_deterministic_exact_revision(tmp_path: Path) -> None:
    store = authority(tmp_path, approval_data=approval())

    first = store.get(SCOPE, "agnes-text", revision=1)
    second = store.get(SCOPE, "agnes-text", revision=1)

    assert first == second
    assert first.provider_plugin_id == "agnes-text"
    assert first.revision == 1
    assert first.manifest_version == "0.1.0"
    assert first.approved_capabilities == ["llm", "chat"]
    assert first.denied_capabilities == ["image", "audio", "video", "tool-execution"]
    assert len(first.manifest_source_hash) == 64
    assert len(first.content_hash) == 64
    assert "secret" not in first.model_dump_json().lower()
    assert "api-key" not in first.model_dump_json().lower()


def test_real_approved_agnes_manifest_has_exact_readback() -> None:
    item = ProviderPluginAuthority().get(SCOPE, "agnes-text", revision=1)

    assert item.owner == "AOS/FDE"
    assert item.default_models == ["agnes-2.0-flash"]
    assert item.allowed_tenants[0].org_id == "org-org"


def test_missing_approval_is_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(ProviderPluginAuthorityError) as captured:
        authority(tmp_path).get(SCOPE, "agnes-text")

    assert captured.value.code == "provider_plugin_not_approved"


@pytest.mark.parametrize("drift", ["id", "version", "capabilities"])
def test_manifest_approval_drift_is_rejected(tmp_path: Path, drift: str) -> None:
    data = approval()
    if drift == "id":
        data["providerPluginId"] = "other"
    elif drift == "version":
        data["manifestVersion"] = "9.9.9"
    else:
        data["approvedCapabilities"] = ["llm"]

    with pytest.raises(ProviderPluginAuthorityError) as captured:
        authority(tmp_path, approval_data=data).get(SCOPE, "agnes-text")

    assert captured.value.code == "provider_plugin_approval_drifted"


def test_content_hash_changes_when_approved_content_changes(tmp_path: Path) -> None:
    first = authority(tmp_path / "a", approval_data=approval()).get(SCOPE, "agnes-text")
    changed = approval()
    changed["usageBasis"] = "different reviewed basis"
    second = authority(tmp_path / "b", approval_data=changed).get(SCOPE, "agnes-text")

    assert first.manifest_source_hash == second.manifest_source_hash
    assert first.content_hash != second.content_hash


def test_negative_tenant_canary_cannot_read_or_validate_revision(tmp_path: Path) -> None:
    store = authority(tmp_path, approval_data=approval())
    exact = store.get(SCOPE, "agnes-text")
    exact_ref = VersionedAssetRef(
        assetType="ProviderPluginRevision",
        assetId=exact.provider_plugin_id,
        revision=exact.revision,
        contentHash=exact.content_hash,
    )

    with pytest.raises(ProviderPluginAuthorityError) as captured:
        store.get(CANARY, "agnes-text")
    assert captured.value.code == "provider_plugin_scope_not_approved"

    with pytest.raises(ProviderPluginAuthorityError) as captured:
        store.validate_ref(CANARY, exact_ref)
    assert captured.value.code == "provider_plugin_scope_not_approved"


def test_exact_ref_validation_rejects_revision_hash_or_kind_drift(tmp_path: Path) -> None:
    store = authority(tmp_path, approval_data=approval())
    item = store.get(SCOPE, "agnes-text")

    for kind, revision, content_hash in (
        ("WrongRevision", 1, item.content_hash),
        ("ProviderPluginRevision", 2, item.content_hash),
        ("ProviderPluginRevision", 1, "f" * 64),
    ):
        with pytest.raises(ProviderPluginAuthorityError) as captured:
            store.validate_ref(
                SCOPE,
                VersionedAssetRef(
                    assetType=kind,
                    assetId="agnes-text",
                    revision=revision,
                    contentHash=content_hash,
                ),
            )
        assert captured.value.code == "provider_plugin_ref_drifted"

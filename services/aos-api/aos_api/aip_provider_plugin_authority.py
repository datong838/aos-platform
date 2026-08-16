"""Deterministic read-only authority for approved AIP provider plugins."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import Field, ValidationError

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.tenant_scope import TenantScope


_PLUGIN_ID = re.compile(r"^[a-z][a-z0-9-]{1,63}$")


class ProviderPluginAuthorityError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class _ProviderManifest(AipContractModel):
    id: str = Field(min_length=1, max_length=64)
    name: str
    name_zh: str
    description: str
    tier: str
    modalities: list[str] = Field(min_length=1)
    capabilities: list[str] = Field(min_length=1)
    form_family: str
    default_models: list[str] = Field(min_length=1)
    litellm_prefix: str
    version: str = Field(min_length=1)
    author: str
    config_schema: dict[str, Any]


class _ProviderApproval(AipContractModel):
    schema_: str = Field(alias="schema")
    provider_plugin_id: str
    revision: int = Field(ge=1)
    manifest_version: str
    owner: str
    usage_basis: str
    approved_capabilities: list[str] = Field(min_length=1)
    denied_capabilities: list[str]
    allowed_tenants: list[TenantContext] = Field(min_length=1)
    approval_status: str
    approved_by: str
    approved_at: datetime


class ProviderPluginRevision(AipContractModel):
    provider_plugin_id: str
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_version: str
    manifest_source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_ref: str
    owner: str
    usage_basis: str
    approved_capabilities: list[str]
    denied_capabilities: list[str]
    modalities: list[str]
    default_models: list[str]
    allowed_tenants: list[TenantContext]
    approval_status: str
    approved_by: str
    approved_at: datetime


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ProviderPluginAuthority:
    """Build immutable approved revisions from a manifest and approval sidecar."""

    def __init__(self, *, root: Path | None = None) -> None:
        self._root = root or Path(__file__).resolve().parents[3] / "plugins" / "llm-providers"

    def get(
        self,
        scope: TenantScope,
        plugin_id: str,
        revision: int | None = None,
    ) -> ProviderPluginRevision:
        if not _PLUGIN_ID.fullmatch(plugin_id):
            raise ProviderPluginAuthorityError("provider_plugin_not_found")
        directory = self._root / plugin_id
        manifest_path = directory / "manifest.json"
        approval_path = directory / "approval.json"
        if not manifest_path.is_file():
            raise ProviderPluginAuthorityError("provider_plugin_not_found")
        if not approval_path.is_file():
            raise ProviderPluginAuthorityError("provider_plugin_not_approved")

        manifest_raw = self._read_bytes(manifest_path, "provider_plugin_manifest_invalid")
        approval_raw = self._read_bytes(approval_path, "provider_plugin_approval_invalid")
        try:
            manifest = _ProviderManifest.model_validate_json(manifest_raw)
            approval = _ProviderApproval.model_validate_json(approval_raw)
        except (ValidationError, ValueError):
            raise ProviderPluginAuthorityError("provider_plugin_metadata_invalid") from None

        self._validate_approval(plugin_id, manifest, approval)
        if revision is not None and revision != approval.revision:
            raise ProviderPluginAuthorityError("provider_plugin_ref_drifted")
        if scope.key not in {
            (tenant.org_id, tenant.project_id) for tenant in approval.allowed_tenants
        }:
            raise ProviderPluginAuthorityError("provider_plugin_scope_not_approved")

        payload = {
            "providerPluginId": plugin_id,
            "revision": approval.revision,
            "manifestVersion": manifest.version,
            "manifestSourceHash": hashlib.sha256(manifest_raw).hexdigest(),
            "sourceRef": f"plugins/llm-providers/{plugin_id}/manifest.json",
            "owner": approval.owner,
            "usageBasis": approval.usage_basis,
            "approvedCapabilities": approval.approved_capabilities,
            "deniedCapabilities": approval.denied_capabilities,
            "modalities": manifest.modalities,
            "defaultModels": manifest.default_models,
            "allowedTenants": [
                tenant.model_dump(mode="json", by_alias=True)
                for tenant in approval.allowed_tenants
            ],
            "approvalStatus": approval.approval_status,
            "approvedBy": approval.approved_by,
            "approvedAt": approval.approved_at.isoformat(),
        }
        return ProviderPluginRevision(
            **payload,
            contentHash=_canonical_hash(payload),
        )

    def validate_ref(self, scope: TenantScope, ref: VersionedAssetRef) -> ProviderPluginRevision:
        if ref.asset_type != "ProviderPluginRevision":
            raise ProviderPluginAuthorityError("provider_plugin_ref_drifted")
        item = self.get(scope, ref.asset_id, ref.revision)
        if item.content_hash != ref.content_hash:
            raise ProviderPluginAuthorityError("provider_plugin_ref_drifted")
        return item

    @staticmethod
    def _read_bytes(path: Path, code: str) -> bytes:
        try:
            return path.read_bytes()
        except OSError:
            raise ProviderPluginAuthorityError(code) from None

    @staticmethod
    def _validate_approval(
        plugin_id: str,
        manifest: _ProviderManifest,
        approval: _ProviderApproval,
    ) -> None:
        approved = approval.approved_capabilities
        denied = approval.denied_capabilities
        if (
            approval.schema_ != "aos-provider-plugin-approval/v1"
            or approval.approval_status != "approved_for_dev"
            or manifest.id != plugin_id
            or approval.provider_plugin_id != plugin_id
            or approval.manifest_version != manifest.version
            or set(approved) != set(manifest.capabilities)
            or len(approved) != len(set(approved))
            or len(manifest.capabilities) != len(set(manifest.capabilities))
            or len(manifest.modalities) != len(set(manifest.modalities))
            or len(manifest.default_models) != len(set(manifest.default_models))
            or len(denied) != len(set(denied))
            or set(approved) & set(denied)
        ):
            raise ProviderPluginAuthorityError("provider_plugin_approval_drifted")

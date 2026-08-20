"""Helpers for W-D3 capability tool-dependency attachment."""

from __future__ import annotations

from aos_api.aip_agent_registry_contracts import VersionedAssetRef

TOOL_ASSET_TYPE = "EvidenceBundleRevision"


def tool_ref_for(bundle_id: str, revision: int, content_hash: str) -> VersionedAssetRef:
    return VersionedAssetRef(
        asset_type=TOOL_ASSET_TYPE,
        asset_id=bundle_id,
        revision=revision,
        content_hash=content_hash,
    )

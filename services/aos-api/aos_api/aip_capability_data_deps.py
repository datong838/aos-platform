"""Helpers for W-D2 capability data-dependency attachment."""

from __future__ import annotations

from aos_api.aip_agent_registry_contracts import VersionedAssetRef


DATA_ASSET_TYPE = "EvalDatasetRevision"


def data_ref_for(dataset_id: str, revision: int, content_hash: str) -> VersionedAssetRef:
    return VersionedAssetRef(
        asset_type=DATA_ASSET_TYPE,
        asset_id=dataset_id,
        revision=revision,
        content_hash=content_hash,
    )


def dataset_id_for(capability_id: str) -> str:
    return f"ecommerce.shared.evalset.{capability_id}"

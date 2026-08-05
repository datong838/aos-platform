from __future__ import annotations

from unittest.mock import patch

import pytest

from aos_api.connector_runtime import _file_object_store_probe
from aos_api.errors import ApiError
from aos_api.tenant_prefix import scoped_collection_name


def test_object_store_probe_lists_only_authenticated_prefix() -> None:
    observed: list[str] = []

    def fake_list(*, prefix: str, cfg) -> list[str]:
        observed.append(prefix)
        return [f"{prefix}mediasets/item/blob"]

    with (
        patch("aos_api.object_store.get_config") as config,
        patch("aos_api.object_store.list_keys_with_prefix", side_effect=fake_list),
    ):
        config.return_value.enabled = True
        config.return_value.bucket = "aos-media"
        result = _file_object_store_probe(
            org_id="org-a", project_id="workspace-a", limit=5
        )

    assert observed == ["org-a/workspace-a/"]
    assert result["sample"] == ["org-a/workspace-a/mediasets/item/blob"]
    assert result["orgId"] == "org-a"
    assert result["projectId"] == "workspace-a"


def test_object_store_probe_without_scope_fails_closed() -> None:
    with pytest.raises(ApiError) as error:
        _file_object_store_probe()
    assert error.value.code == "TENANT_SCOPE_REQUIRED"


def test_vector_collection_same_logical_name_is_scoped() -> None:
    a = scoped_collection_name("org-a", "workspace-a", "orders")
    b = scoped_collection_name("org-b", "workspace-b", "orders")
    assert a == "org-a__workspace-a__orders"
    assert b == "org-b__workspace-b__orders"
    assert a != b
    with pytest.raises(ApiError) as error:
        scoped_collection_name("org-b", "workspace-b", a)
    assert error.value.code == "FORBIDDEN"

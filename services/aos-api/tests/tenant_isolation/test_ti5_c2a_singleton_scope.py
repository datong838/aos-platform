from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from aos_api.aip_model_catalog import get_engine as get_catalog_engine
from aos_api.phase5_pipeline_engine import get_engine as get_pipeline_engine
from aos_api.tenant_scope import TenantScope


SCOPE_A = TenantScope("org-a", "workspace-a")
SCOPE_B = TenantScope("org-b", "workspace-b")


def _headers(scope: TenantScope) -> dict[str, str]:
    return {
        "Authorization": "Bearer dev",
        "X-Org-Id": scope.org_id,
        "X-Project-Id": scope.project_id,
    }


@pytest.fixture(autouse=True)
def _reset_singletons() -> None:
    get_catalog_engine().reset_all_for_tests()
    get_pipeline_engine().reset_all_for_tests()
    yield
    get_catalog_engine().reset_all_for_tests()
    get_pipeline_engine().reset_all_for_tests()


def test_model_catalog_same_id_and_reset_are_scope_isolated() -> None:
    engine = get_catalog_engine()
    fixed_uuid = SimpleNamespace(hex="sharedid000000000000000000000000")
    with patch("aos_api.aip_model_catalog.uuid.uuid4", return_value=fixed_uuid):
        item_a = engine.create(SCOPE_A, "catalog-a")
        item_b = engine.create(SCOPE_B, "catalog-b")

    assert item_a.id == item_b.id == "aip-model-catalog-sharedid"
    assert engine.get(SCOPE_A, item_a.id).name == "catalog-a"
    assert engine.get(SCOPE_B, item_b.id).name == "catalog-b"

    engine.reset(SCOPE_A)
    assert engine.get(SCOPE_A, item_a.id) is None
    assert engine.get(SCOPE_B, item_b.id).name == "catalog-b"


def test_model_catalog_capacity_is_counted_per_scope() -> None:
    engine = get_catalog_engine()
    with patch("aos_api.aip_model_catalog._MAX_ITEMS", 1):
        engine.create(SCOPE_A, "a-1")
        engine.create(SCOPE_B, "b-1")
        with pytest.raises(ValueError, match="容量上限"):
            engine.create(SCOPE_A, "a-2")


def test_phase5_dataset_children_and_reset_are_scope_isolated() -> None:
    engine = get_pipeline_engine()
    dataset_a = engine.create_dataset(SCOPE_A, id="shared-dataset", name="A")
    dataset_b = engine.create_dataset(SCOPE_B, id="shared-dataset", name="B")
    engine.add_build(SCOPE_A, dataset_a.id, id="shared-build", status="success")
    engine.add_build(SCOPE_B, dataset_b.id, id="shared-build", status="failed")
    engine.check_health(SCOPE_A, dataset_a.id)
    engine.set_sync_config(SCOPE_A, dataset_a.id, mode="incremental")

    assert engine.get_dataset(SCOPE_A, "shared-dataset").name == "A"
    assert engine.get_dataset(SCOPE_B, "shared-dataset").name == "B"
    assert engine.list_builds(SCOPE_A, "shared-dataset")[0].status == "success"
    assert engine.list_builds(SCOPE_B, "shared-dataset")[0].status == "failed"
    assert engine.get_latest_health(SCOPE_B, "shared-dataset") is None
    assert engine.get_sync_config(SCOPE_B, "shared-dataset").mode == "full"

    engine.reset(scope=SCOPE_A)
    assert engine.get_dataset(SCOPE_A, "shared-dataset") is None
    assert engine.get_dataset(SCOPE_B, "shared-dataset").name == "B"
    assert len(engine.list_builds(SCOPE_B, "shared-dataset")) == 1


def test_singleton_routes_require_auth_and_hide_foreign_scope(client) -> None:
    assert client.get("/api/aip/model-catalog").status_code == 401
    assert client.get("/v1/datasets").status_code == 401

    created_catalog = client.post(
        "/api/aip/model-catalog",
        headers=_headers(SCOPE_A),
        json={"name": "private-model"},
    )
    assert created_catalog.status_code == 200
    catalog_id = created_catalog.json()["id"]
    assert client.get(
        f"/api/aip/model-catalog/{catalog_id}", headers=_headers(SCOPE_B)
    ).status_code == 404

    created_dataset = client.post(
        "/v1/datasets",
        headers=_headers(SCOPE_A),
        json={"name": "private-dataset"},
    )
    assert created_dataset.status_code == 200
    dataset_id = created_dataset.json()["id"]
    assert client.get(
        f"/v1/datasets/{dataset_id}", headers=_headers(SCOPE_B)
    ).status_code == 404
    foreign_list = client.get("/v1/datasets", headers=_headers(SCOPE_B))
    assert foreign_list.status_code == 200
    assert foreign_list.json()["items"] == []

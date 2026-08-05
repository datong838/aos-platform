from __future__ import annotations

import copy
from unittest.mock import patch

import pytest

from aos_api.auth import Principal
from aos_api.errors import ApiError
from aos_api.routers import analytics, wave_ext
from aos_api.tenant_scope import TenantScope


SCOPE_A = TenantScope("org-a", "workspace-a")
SCOPE_B = TenantScope("org-b", "workspace-b")


def _principal(scope: TenantScope) -> Principal:
    return Principal(subject="test", org_id=scope.org_id, project_id=scope.project_id)


@pytest.fixture(autouse=True)
def _restore_wave_ext_state() -> None:
    mappings = (
        "_connectors",
        "_pipelines",
        "_schedules",
        "_syncs",
        "_datasets",
        "_dataset_history",
        "_media",
        "_media_bytes",
    )
    snapshots = {name: copy.deepcopy(getattr(wave_ext, name)) for name in mappings}
    loaded = set(wave_ext._data_os_loaded_scopes)
    dlq = copy.deepcopy(wave_ext._dlq)
    for name in mappings:
        getattr(wave_ext, name).clear()
    wave_ext._data_os_loaded_scopes.clear()
    wave_ext._dlq.clear()
    yield
    for name in mappings:
        mapping = getattr(wave_ext, name)
        mapping.clear()
        mapping.update(snapshots[name])
    wave_ext._data_os_loaded_scopes.clear()
    wave_ext._data_os_loaded_scopes.update(loaded)
    wave_ext._dlq[:] = dlq


def test_hydrate_keeps_same_dataset_rid_in_two_scopes() -> None:
    def load(scope: TenantScope) -> dict:
        item = {
            "rid": "shared-dataset",
            "name": scope.org_id,
            "orgId": scope.org_id,
            "projectId": scope.project_id,
        }
        return {
            "connectors": {},
            "pipelines": {},
            "datasets": {"shared-dataset": item},
            "syncs": {},
            "schedules": {},
            "dataset_history": {"shared-dataset": [{"scope": scope.org_id}]},
        }

    with patch("aos_api.data_os_store.load_all", side_effect=load):
        wave_ext._hydrate_data_os_scope(SCOPE_A, force=True)
        wave_ext._hydrate_data_os_scope(SCOPE_B, force=True)

    key_a = wave_ext._resource_key(SCOPE_A, "shared-dataset")
    key_b = wave_ext._resource_key(SCOPE_B, "shared-dataset")
    assert wave_ext._datasets[key_a]["name"] == "org-a"
    assert wave_ext._datasets[key_b]["name"] == "org-b"
    assert wave_ext._dataset_history[key_a] == [{"scope": "org-a"}]
    assert wave_ext._dataset_history[key_b] == [{"scope": "org-b"}]


def test_dataset_routes_and_analytics_use_scope_key() -> None:
    rid = "shared-dataset"
    for scope in (SCOPE_A, SCOPE_B):
        key = wave_ext._resource_key(scope, rid)
        wave_ext._datasets[key] = {
            "rid": rid,
            "name": scope.org_id,
            "orgId": scope.org_id,
            "projectId": scope.project_id,
        }
        wave_ext._dataset_history[key] = [{"scope": scope.org_id}]
        wave_ext._data_os_loaded_scopes.add(scope.key)

    assert wave_ext.get_dataset(rid, _principal(SCOPE_A))["name"] == "org-a"
    assert wave_ext.dataset_history(rid, _principal(SCOPE_B))["items"] == [
        {"scope": "org-b"}
    ]
    assert analytics._lookup_dataset(_principal(SCOPE_A), rid)["name"] == "org-a"
    assert analytics._lookup_dataset(_principal(SCOPE_B), rid)["name"] == "org-b"


def test_media_metadata_bytes_and_parse_are_scope_isolated() -> None:
    rid = "shared-media"
    for scope, raw in ((SCOPE_A, b"bytes-a"), (SCOPE_B, b"bytes-b")):
        key = wave_ext._resource_key(scope, rid)
        wave_ext._media[key] = {
            "rid": rid,
            "name": scope.org_id,
            "contentType": "text/plain",
            "orgId": scope.org_id,
            "projectId": scope.project_id,
        }
        wave_ext._media_bytes[key] = raw

    with patch(
        "aos_api.file_parsers.extract",
        side_effect=lambda *, data, **_: {"ok": True, "preview": data.decode()},
    ):
        parsed_a = wave_ext.parsers_extract(
            {"mediaRid": rid}, _principal(SCOPE_A)
        )
        parsed_b = wave_ext.parsers_extract(
            {"mediaRid": rid}, _principal(SCOPE_B)
        )

    assert parsed_a["preview"] == "bytes-a"
    assert parsed_b["preview"] == "bytes-b"
    assert wave_ext.get_media(rid, _principal(SCOPE_A))["name"] == "org-a"
    assert wave_ext.media_ref(rid, _principal(SCOPE_B))["name"] == "org-b"


def test_foreign_media_rid_fails_closed_in_parser_and_docintel() -> None:
    rid = "private-media"
    key_b = wave_ext._resource_key(SCOPE_B, rid)
    wave_ext._media[key_b] = {"rid": rid, "name": "b"}
    wave_ext._media_bytes[key_b] = b"secret-b"

    with pytest.raises(ApiError) as parser_error:
        wave_ext.parsers_extract({"mediaRid": rid}, _principal(SCOPE_A))
    assert parser_error.value.status_code == 404

    with pytest.raises(ApiError) as docintel_error:
        wave_ext.docintel_pipeline({"mediaRid": rid}, _principal(SCOPE_A))
    assert docintel_error.value.status_code == 404


def test_demo_seed_requires_scope_and_keeps_dataset_per_scope() -> None:
    with pytest.raises(TypeError):
        wave_ext.ensure_demo_data_seed(force=True)

    wave_ext.ensure_demo_data_seed(SCOPE_A, force=True)
    wave_ext.ensure_demo_data_seed(SCOPE_B, force=True)
    rid = "ri.dataset.demo-workorder"
    assert wave_ext._resource_key(SCOPE_A, rid) in wave_ext._datasets
    assert wave_ext._resource_key(SCOPE_B, rid) in wave_ext._datasets
    assert SCOPE_A.key in wave_ext._data_os_loaded_scopes
    assert SCOPE_B.key in wave_ext._data_os_loaded_scopes

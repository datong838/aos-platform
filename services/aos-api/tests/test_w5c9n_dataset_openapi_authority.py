"""Dataset docs show the reachable GETs without changing route dispatch."""

from fastapi.routing import iter_route_contexts

from aos_api.main import app


def _contexts(method: str, path: str):
    return [
        item for item in iter_route_contexts(app.routes)
        if item.path == path and item.methods and method in item.methods
    ]


def test_dataset_get_documentation_uses_first_reachable_owner() -> None:
    listing = _contexts("GET", "/v1/datasets")
    detail = _contexts("GET", "/v1/datasets/{rid}") + _contexts(
        "GET", "/v1/datasets/{ds_id}"
    )
    assert [item.endpoint.__module__ for item in listing] == [
        "aos_api.routers.wave_ext", "aos_api.routers.phase5_datasets"
    ]
    assert [item.endpoint.__module__ for item in detail] == [
        "aos_api.routers.wave_ext", "aos_api.routers.phase5_datasets"
    ]
    assert [item.include_in_schema for item in listing] == [True, False]
    assert [item.include_in_schema for item in detail] == [True, False]

    schema = app.openapi()
    listing_doc = schema["paths"]["/v1/datasets"]["get"]
    detail_doc = schema["paths"]["/v1/datasets/{rid}"]["get"]
    assert "wave3-plus" in listing_doc["tags"]
    assert "wave3-plus" in detail_doc["tags"]
    assert "/v1/datasets/{ds_id}" not in schema["paths"]
    assert "post" in schema["paths"]["/v1/datasets"]
    assert "get" in schema["paths"]["/v1/datasets/{ds_id}/preview"]

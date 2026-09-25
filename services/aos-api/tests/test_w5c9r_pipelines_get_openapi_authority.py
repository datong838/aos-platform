"""Pipeline listing docs show its first reachable GET without changing POST."""

from fastapi.routing import iter_route_contexts

from aos_api.main import app


def test_pipeline_listing_documentation_uses_first_reachable_get() -> None:
    routes = [
        item for item in iter_route_contexts(app.routes)
        if item.path == "/v1/pipelines" and item.methods and "GET" in item.methods
    ]
    assert [item.endpoint.__module__ for item in routes] == [
        "aos_api.routers.wave_ext", "aos_api.routers.phase5_pipelines"
    ]
    assert [item.include_in_schema for item in routes] == [True, False]

    schema = app.openapi()
    assert "wave3-plus" in schema["paths"]["/v1/pipelines"]["get"]["tags"]
    assert "post" in schema["paths"]["/v1/pipelines"]
    assert "get" in schema["paths"]["/v1/pipelines/{pl_id}"]

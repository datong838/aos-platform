"""Builds listing docs must describe the first reachable route only."""

from fastapi.routing import iter_route_contexts

from aos_api.main import app


def test_builds_listing_documentation_uses_first_reachable_owner() -> None:
    routes = [
        item for item in iter_route_contexts(app.routes)
        if item.path == "/v1/builds" and item.methods and "GET" in item.methods
    ]
    assert [item.endpoint.__module__ for item in routes] == [
        "aos_api.routers.wave_ext", "aos_api.routers.builds"
    ]
    assert [item.include_in_schema for item in routes] == [True, False]

    schema = app.openapi()
    assert "wave3-plus" in schema["paths"]["/v1/builds"]["get"]["tags"]
    assert "post" in schema["paths"]["/v1/builds"]
    assert "get" in schema["paths"]["/v1/builds/dlq"]
    assert "post" in schema["paths"]["/v1/builds/{job_id}/cancel"]

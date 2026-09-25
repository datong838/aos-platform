"""Schedules listing docs describe the first reachable GET only."""

from fastapi.routing import iter_route_contexts

from aos_api.main import app


def test_schedule_listing_documentation_uses_first_reachable_get() -> None:
    routes = [
        item for item in iter_route_contexts(app.routes)
        if item.path == "/v1/schedules" and item.methods and "GET" in item.methods
    ]
    assert [item.endpoint.__module__ for item in routes] == [
        "aos_api.routers.wave_ext", "aos_api.routers.phase5_schedules"
    ]
    assert [item.include_in_schema for item in routes] == [True, False]

    schema = app.openapi()
    assert "wave3-plus" in schema["paths"]["/v1/schedules"]["get"]["tags"]
    assert "post" in schema["paths"]["/v1/schedules"]
    assert "post" in schema["paths"]["/v1/schedules/{sc_id}/pause"]

"""Write shape aliases must not document unreachable handlers or execute them."""

import pytest
from fastapi.routing import iter_route_contexts
from starlette.routing import Match

from aos_api.main import app


@pytest.mark.parametrize(
    ("method", "sample_path", "first_path", "later_path", "first_module", "later_module"),
    [
        (
            "PUT", "/v1/ontology/object-types/probe",
            "/v1/ontology/object-types/{type_id}",
            "/v1/ontology/object-types/{ot_id}",
            "aos_api.routers.ontology", "aos_api.routers.phase4_ontology_types",
        ),
        (
            "POST", "/v1/schedules/probe/run",
            "/v1/schedules/{schedule_id}/run",
            "/v1/schedules/{sc_id}/run",
            "aos_api.routers.wave_ext", "aos_api.routers.phase5_schedules",
        ),
    ],
)
def test_shape_write_documentation_uses_first_reachable_handler(
    method, sample_path, first_path, later_path, first_module, later_module
) -> None:
    # Route matcher only: never create an HTTP request or call an endpoint.
    scope = {"type": "http", "path": sample_path, "method": method, "root_path": ""}
    matches = [
        item for item in iter_route_contexts(app.routes)
        if item.matches(scope)[0] is Match.FULL and item.methods and method in item.methods
    ]
    assert [item.path for item in matches] == [first_path, later_path]
    assert [item.endpoint.__module__ for item in matches] == [first_module, later_module]
    assert [item.include_in_schema for item in matches] == [True, False]

    paths = app.openapi()["paths"]
    assert method.lower() in paths[first_path]
    assert method.lower() not in paths.get(later_path, {})


def test_independent_read_and_write_documentation_remains() -> None:
    paths = app.openapi()["paths"]
    assert "get" in paths["/v1/ontology/object-types/{type_id}"]
    assert "get" in paths["/v1/ontology/object-types/{ot_id}/count"]
    assert "get" in paths["/v1/schedules/{schedule_id}"]
    assert "get" in paths["/v1/schedules/{schedule_id}/runs"]
    assert "put" in paths["/v1/schedules/{sc_id}"]
    assert "post" in paths["/v1/schedules/{sc_id}/pause"]

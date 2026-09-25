"""Shape-colliding GET docs describe the reachable first handlers only."""

import pytest
from fastapi.routing import iter_route_contexts
from starlette.routing import Match

from aos_api.main import app


@pytest.mark.parametrize(
    ("sample_path", "first_path", "later_path", "first_module", "later_module"),
    [
        (
            "/v1/aip/lineage/probe",
            "/v1/aip/lineage/{lineage_id}",
            "/v1/aip/lineage/{record_id}",
            "aos_api.routers.runtime_write",
            "aos_api.routers.phase3_aip_lineage",
        ),
        (
            "/v1/ontology/object-types/probe",
            "/v1/ontology/object-types/{type_id}",
            "/v1/ontology/object-types/{ot_id}",
            "aos_api.routers.ontology",
            "aos_api.routers.phase4_ontology_types",
        ),
        (
            "/v1/schedules/probe",
            "/v1/schedules/{schedule_id}",
            "/v1/schedules/{sc_id}",
            "aos_api.routers.wave_ext",
            "aos_api.routers.phase5_schedules",
        ),
        (
            "/v1/schedules/probe/runs",
            "/v1/schedules/{schedule_id}/runs",
            "/v1/schedules/{sc_id}/runs",
            "aos_api.routers.wave_ext",
            "aos_api.routers.phase5_schedules",
        ),
    ],
)
def test_shape_get_documentation_uses_first_reachable_handler(
    sample_path, first_path, later_path, first_module, later_module
) -> None:
    scope = {"type": "http", "path": sample_path, "method": "GET", "root_path": ""}
    matches = [
        item for item in iter_route_contexts(app.routes)
        if item.matches(scope)[0] is Match.FULL and item.methods and "GET" in item.methods
    ]
    assert [item.path for item in matches] == [first_path, later_path]
    assert [item.endpoint.__module__ for item in matches] == [first_module, later_module]
    assert [item.include_in_schema for item in matches] == [True, False]

    paths = app.openapi()["paths"]
    assert "get" in paths[first_path]
    assert "get" not in paths.get(later_path, {})


def test_unrelated_read_and_write_documentation_remains() -> None:
    paths = app.openapi()["paths"]
    assert "get" in paths["/v1/aip/lineage"]
    assert "get" in paths["/v1/ontology/object-types/{ot_id}/count"]
    assert "put" in paths["/v1/ontology/object-types/{ot_id}"]
    assert "put" in paths["/v1/schedules/{sc_id}"]
    assert "post" in paths["/v1/schedules/{sc_id}/run"]
    assert "post" in paths["/v1/schedules/{sc_id}/pause"]

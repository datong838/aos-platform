"""Exact duplicate POST docs must not advertise unreachable write handlers."""

import pytest
from fastapi.routing import iter_route_contexts

from aos_api.main import app


@pytest.mark.parametrize(
    ("path", "first_module", "later_module", "first_tag"),
    [
        ("/v1/ontology/branches", "aos_api.routers.ontology",
         "aos_api.routers.phase4_ontology_branches", "ontology"),
        ("/v1/pipelines", "aos_api.routers.wave_ext",
         "aos_api.routers.phase5_pipelines", "wave3-plus"),
        ("/v1/schedules", "aos_api.routers.wave_ext",
         "aos_api.routers.phase5_schedules", "wave3-plus"),
    ],
)
def test_post_documentation_uses_first_reachable_handler(
    path, first_module, later_module, first_tag
) -> None:
    routes = [
        item for item in iter_route_contexts(app.routes)
        if item.path == path and item.methods and "POST" in item.methods
    ]
    assert [item.endpoint.__module__ for item in routes] == [first_module, later_module]
    assert [item.include_in_schema for item in routes] == [True, False]
    assert first_tag in app.openapi()["paths"][path]["post"]["tags"]
    assert "get" in app.openapi()["paths"][path]


def test_other_write_documentation_is_preserved() -> None:
    paths = app.openapi()["paths"]
    assert "post" in paths["/v1/ontology/branches/{branch_id}/merge"]
    assert "post" in paths["/v1/pipelines/{pl_id}/proposals"]
    assert "post" in paths["/v1/schedules/{sc_id}/pause"]

"""Ontology duplicate GET docs describe only reachable first handlers."""

import pytest
from fastapi.routing import iter_route_contexts

from aos_api.main import app


@pytest.mark.parametrize(
    ("path", "later_module"),
    [
        ("/v1/ontology/branches", "aos_api.routers.phase4_ontology_branches"),
        ("/v1/ontology/graph-health", "aos_api.routers.phase4_ontology_branches"),
        ("/v1/ontology/object-types", "aos_api.routers.phase4_ontology_types"),
    ],
)
def test_ontology_get_documentation_uses_first_reachable_owner(path, later_module) -> None:
    routes = [
        item for item in iter_route_contexts(app.routes)
        if item.path == path and item.methods and "GET" in item.methods
    ]
    assert [item.endpoint.__module__ for item in routes] == [
        "aos_api.routers.ontology", later_module
    ]
    assert [item.include_in_schema for item in routes] == [True, False]
    assert "ontology" in app.openapi()["paths"][path]["get"]["tags"]


def test_ontology_write_and_unique_phase4_docs_are_not_hidden() -> None:
    paths = app.openapi()["paths"]
    assert "post" in paths["/v1/ontology/branches"]
    assert "put" in paths["/v1/ontology/object-types/{ot_id}"]
    assert "get" in paths["/v1/ontology/recent"]

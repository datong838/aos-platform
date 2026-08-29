from aos_api.routers.domain_aggregates import ROUTER_SPECS
from aos_api.routers.ontology_overlay import router


def test_ontology_overlay_routes_are_registered_in_domain_router() -> None:
    assert ("aos_api.routers.ontology_overlay", "router") in ROUTER_SPECS["ontology"]
    routes = {
        (route.path, method)
        for route in router.routes
        for method in route.methods
    }

    base = "/v1/ontology/installations/{installation_pk}/overlays"
    assert (base, "GET") in routes
    assert (f"{base}/history", "GET") in routes
    assert (f"{base}/{{target_kind}}/{{target_id}}", "PUT") in routes

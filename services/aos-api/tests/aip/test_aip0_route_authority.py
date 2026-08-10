from __future__ import annotations

from collections import Counter

from aos_api.main import app


AIP_AUTHORITIES = {
    ("GET", "/v1/aip/capabilities"): "list_caps",
    ("POST", "/v1/aip/circuit/trip"): "circuit_trip",
    ("GET", "/v1/aip/drafts"): "list_drafts",
    ("GET", "/v1/aip/drafts/{draft_id}"): "get_draft",
    ("POST", "/v1/aip/drafts/{draft_id}/approve"): "approve_draft",
    ("POST", "/v1/aip/drafts/{draft_id}/reject"): "reject_draft",
    ("GET", "/v1/aip/evals"): "evals_get",
    ("GET", "/v1/aip/insights"): "list_insights",
    ("GET", "/v1/aip/tools"): "list_tools",
}


def _effective_routes(routes):
    for route in routes:
        candidates = getattr(route, "effective_candidates", None)
        if callable(candidates):
            yield from _effective_routes(candidates())
        else:
            yield route


def test_aip_public_routes_have_one_authority():
    observed = []
    names = {}
    for route in _effective_routes(app.routes):
        path = getattr(route, "path", "")
        for method in set(getattr(route, "methods", set())) - {"HEAD", "OPTIONS"}:
            key = (method, path)
            observed.append(key)
            names[key] = route.name
    counts = Counter(observed)
    assert not [key for key, count in counts.items() if count > 1 and key[1].startswith("/v1/aip/")]
    for key, expected_name in AIP_AUTHORITIES.items():
        assert counts[key] == 1
        assert names[key] == expected_name


def test_legacy_generic_draft_transition_is_not_public():
    paths = {
        (method, route.path)
        for route in _effective_routes(app.routes)
        for method in set(getattr(route, "methods", set())) - {"HEAD", "OPTIONS"}
    }
    assert ("POST", "/v1/aip/drafts/{draft_id}/transition") not in paths


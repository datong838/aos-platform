from pathlib import Path

from aos_api.routers import ecommerce_business_investigations
from aos_api.routers import ecommerce_workshop
from aos_api.routers.extension_dispatch import router


SOURCE = (
    Path(__file__).resolve().parents[2]
    / "aos_api"
    / "routers"
    / "extension_dispatch.py"
)
READ_ONLY_METHODS = {"GET", "HEAD"}


def _effective_routes(routes):
    for route in routes:
        candidates = getattr(route, "effective_candidates", None)
        if callable(candidates):
            yield from _effective_routes(candidates())
        else:
            yield route


def _operation_list(source):
    return [
        (route.path, method)
        for route in _effective_routes(source.routes)
        for method in (getattr(route, "methods", None) or set())
    ]


def _operations(source):
    return set(_operation_list(source))


def test_extension_dispatch_has_no_domain_sql_or_route_handlers() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "SELECT " not in source
    assert "INSERT " not in source
    assert "UPDATE " not in source
    assert "DELETE " not in source
    assert "@router." not in source


def test_extension_dispatch_keeps_legacy_reads_and_removes_legacy_writes() -> None:
    effective = _operations(router)
    legacy = _operations(ecommerce_workshop.router) | _operations(
        ecommerce_business_investigations.router
    )
    legacy_reads = {
        operation for operation in legacy if operation[1] in READ_ONLY_METHODS
    }
    legacy_writes = legacy - legacy_reads

    assert legacy_reads <= effective
    assert effective.isdisjoint(legacy_writes)


def test_extension_dispatch_exposes_one_canonical_write_path() -> None:
    operations = _operation_list(router)
    canonical = (
        "/v1/ecommerce-growth/operations/{operation_id}",
        "POST",
    )
    assert canonical in operations
    assert sum(operation == canonical for operation in operations) == 1

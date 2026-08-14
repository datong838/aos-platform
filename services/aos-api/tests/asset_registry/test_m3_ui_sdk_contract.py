"""M3-0 OpenAPI contract freeze for the installation management UI/SDK.

These tests intentionally exercise only schema generation.  They protect the thin
M3 client from path, operation, authentication, concurrency-header, and error
contract drift without invoking a database-backed control service.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from aos_api.routers import (
    asset_bundles,
    bundle_compositions,
    bundle_installations,
)

CONTROL_OPERATIONS = {
    ("post", "/v1/bundle-compositions:resolve"): "resolve_bundle_composition",
    (
        "get",
        "/v1/bundle-compositions/{composition_id}/locks/{revision}",
    ): "get_bundle_composition_lock",
    ("post", "/v1/bundle-installations"): "create_bundle_installation",
    ("get", "/v1/bundle-installations"): "list_bundle_installations",
    (
        "get",
        "/v1/bundle-installations/{installation_id}",
    ): "get_bundle_installation",
    (
        "post",
        "/v1/bundle-installations/{installation_id}/submit",
    ): "submit_bundle_installation",
    (
        "post",
        "/v1/bundle-installations/{installation_id}/approve",
    ): "approve_bundle_installation",
    (
        "post",
        "/v1/bundle-installations/{installation_id}/reject",
    ): "reject_bundle_installation",
    (
        "post",
        "/v1/bundle-installations/{installation_id}/apply",
    ): "apply_bundle_installation",
    (
        "post",
        "/v1/bundle-installations/{installation_id}/verify",
    ): "verify_bundle_installation",
    (
        "post",
        "/v1/bundle-installations/{installation_id}/rollback",
    ): "rollback_bundle_installation",
    (
        "post",
        "/v1/bundle-installations/{installation_id}/uninstall",
    ): "uninstall_bundle_installation",
}
COMPOSITION_ERROR_RESPONSES = {"400", "401", "403", "404", "409", "500"}
INSTALLATION_BASE_ERROR_RESPONSES = {
    "400",
    "401",
    "403",
    "404",
    "500",
}
INSTALLATION_COMMAND_ERROR_RESPONSES = INSTALLATION_BASE_ERROR_RESPONSES | {"409"}
INSTALLATION_ACTION_ERROR_RESPONSES = INSTALLATION_COMMAND_ERROR_RESPONSES | {
    "412",
    "428",
}
ACTION_PATHS = {
    f"/v1/bundle-installations/{{installation_id}}/{action}"
    for action in (
        "submit",
        "approve",
        "reject",
        "apply",
        "verify",
        "rollback",
        "uninstall",
    )
}


def _schema() -> dict[str, Any]:
    app = FastAPI()
    app.include_router(asset_bundles.router)
    app.include_router(bundle_compositions.router)
    app.include_router(bundle_installations.router)
    return app.openapi()


def _operation(
    schema: dict[str, Any], method: str, path: str
) -> dict[str, Any]:
    return schema["paths"][path][method]


def _header_parameters(operation: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        parameter["name"]: parameter
        for parameter in operation.get("parameters", [])
        if parameter.get("in") == "header"
    }


def test_control_plane_freezes_exactly_twelve_operation_ids_and_paths() -> None:
    schema = _schema()
    actual = {
        (method, path): operation["operationId"]
        for path, path_item in schema["paths"].items()
        if path.startswith(
            ("/v1/bundle-compositions", "/v1/bundle-installations")
        )
        for method, operation in path_item.items()
        if method in {"get", "post"}
    }

    assert actual == CONTROL_OPERATIONS


def test_every_control_operation_requires_bearer_security() -> None:
    schema = _schema()
    security_scheme_names = set(schema["components"]["securitySchemes"])

    assert security_scheme_names
    for method, path in CONTROL_OPERATIONS:
        operation = _operation(schema, method, path)
        assert operation.get("security"), (method, path)
        assert all(requirement for requirement in operation["security"]), (
            method,
            path,
        )
        assert {
            scheme
            for requirement in operation["security"]
            for scheme in requirement
        } <= security_scheme_names


def test_mutations_freeze_idempotency_and_if_match_headers() -> None:
    schema = _schema()
    idempotent_paths = {
        "/v1/bundle-compositions:resolve",
        "/v1/bundle-installations",
        *ACTION_PATHS,
    }

    for path in idempotent_paths:
        headers = _header_parameters(_operation(schema, "post", path))
        key = headers["Idempotency-Key"]
        assert key["required"] is True
        assert key["schema"] == {
            "type": "string",
            "minLength": 1,
            "maxLength": 160,
        }

    for path in ACTION_PATHS:
        headers = _header_parameters(_operation(schema, "post", path))
        if_match = headers["If-Match"]
        assert if_match["required"] is True
        assert if_match["schema"] == {
            "type": "string",
            "pattern": '^"[1-9][0-9]*"$',
        }

    assert "If-Match" not in _header_parameters(
        _operation(schema, "post", "/v1/bundle-installations")
    )
    assert "If-Match" not in _header_parameters(
        _operation(schema, "post", "/v1/bundle-compositions:resolve")
    )


def test_installation_etag_response_contract_is_explicit() -> None:
    schema = _schema()
    etag_operations = {
        ("post", "/v1/bundle-installations", "201"),
        ("get", "/v1/bundle-installations/{installation_id}", "200"),
        *(("post", path, "200") for path in ACTION_PATHS),
    }

    for method, path, status_code in etag_operations:
        response = _operation(schema, method, path)["responses"][status_code]
        assert response["headers"]["ETag"]["schema"]["type"] == "string"

    assert "headers" not in _operation(
        schema, "get", "/v1/bundle-installations"
    )["responses"]["200"]
    for method, path in (
        ("post", "/v1/bundle-compositions:resolve"),
        ("get", "/v1/bundle-compositions/{composition_id}/locks/{revision}"),
    ):
        assert "headers" not in _operation(schema, method, path)["responses"][
            "201" if method == "post" else "200"
        ]


def test_control_plane_freezes_error_response_sets_and_body_schema() -> None:
    schema = _schema()

    for method, path in CONTROL_OPERATIONS:
        operation = _operation(schema, method, path)
        error_codes = {
            status_code
            for status_code in operation["responses"]
            if status_code[0] in {"4", "5"}
        }
        if path.startswith("/v1/bundle-compositions"):
            expected = COMPOSITION_ERROR_RESPONSES
        elif path in ACTION_PATHS:
            expected = INSTALLATION_ACTION_ERROR_RESPONSES
        elif method == "post":
            expected = INSTALLATION_COMMAND_ERROR_RESPONSES
        else:
            expected = INSTALLATION_BASE_ERROR_RESPONSES
        # FastAPI may additionally publish framework validation response 422.
        assert error_codes == expected | {"422"}
        for status_code in expected:
            error_schema = operation["responses"][status_code]["content"][
                "application/json"
            ]["schema"]
            assert error_schema == {"$ref": "#/components/schemas/ErrorBody"}

    error_body = schema["components"]["schemas"]["ErrorBody"]
    assert set(error_body["required"]) == {"code", "message", "traceId"}
    assert set(error_body["properties"]) == {
        "code",
        "message",
        "details",
        "traceId",
    }


def test_registry_get_schema_records_dynamic_response_limitation() -> None:
    """Registry GETs are intentionally dynamic dicts, not frozen DTO schemas.

    M3 must obtain field-level TypeScript fixtures from real responses and registry
    service/store facts; OpenAPI only promises an object (or array of objects).
    """

    schema = _schema()
    list_response = _operation(schema, "get", "/v1/asset-bundles")["responses"][
        "200"
    ]["content"]["application/json"]["schema"]
    detail_response = _operation(
        schema, "get", "/v1/asset-bundles/{bundle_id}"
    )["responses"]["200"]["content"]["application/json"]["schema"]
    version_response = _operation(
        schema,
        "get",
        "/v1/asset-bundles/{bundle_id}/versions/{version}",
    )["responses"]["200"]["content"]["application/json"]["schema"]

    assert list_response["type"] == "array"
    assert list_response["items"]["type"] == "object"
    assert list_response["items"]["additionalProperties"] is True
    for response_schema in (detail_response, version_response):
        assert response_schema["type"] == "object"
        assert response_schema["additionalProperties"] is True
        assert "properties" not in response_schema

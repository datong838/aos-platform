"""Stable error envelope and fail-closed recursive redaction."""
import logging

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, model_validator

from aos_api.errors import ApiError, error_payload, register_exception_handlers


class SecretBody(BaseModel):
    count: int
    password: str


class CrossFieldBody(BaseModel):
    resource_type: str

    @model_validator(mode="after")
    def _supported(self) -> "CrossFieldBody":
        if self.resource_type != "ExpectedRevision":
            raise ValueError("resource type is not supported")
        return self


def _client(caplog=None) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/api")
    def api_error():
        raise ApiError(
            code="BAD_INPUT", message="Bearer hidden-token user@example.com",
            details={"secret": "do-not-show"}, status_code=400,
        )

    @app.get("/http")
    def http_error():
        raise HTTPException(409, {"code": "CONFLICT", "message": "conflict"})

    @app.post("/validation")
    def validation(body: SecretBody):
        return body

    @app.post("/cross-field-validation")
    def cross_field_validation(body: CrossFieldBody):
        return body

    @app.get("/unknown")
    def unknown():
        raise RuntimeError("Bearer private-token user@example.com")

    return TestClient(app, raise_server_exceptions=False)


def _assert_envelope(body: dict) -> None:
    assert set(body) == {"code", "message", "details", "traceId"}


def test_api_and_http_errors_use_stable_envelope_and_redaction(caplog) -> None:
    client = _client()
    with caplog.at_level(logging.INFO):
        api = client.get("/api")
    assert api.status_code == 400
    _assert_envelope(api.json())
    rendered = str(api.json()) + caplog.text
    assert "hidden-token" not in rendered
    assert "user@example.com" not in rendered
    assert "do-not-show" not in rendered

    http = client.get("/http")
    assert http.status_code == 409
    _assert_envelope(http.json())
    assert http.json()["code"] == "CONFLICT"

    direct = error_payload(
        code="DIRECT", message="Bearer direct-secret", details={"password": "hidden"}
    )
    assert "direct-secret" not in str(direct)
    assert "hidden" not in str(direct)


def test_validation_and_unhandled_errors_do_not_echo_sensitive_input(caplog) -> None:
    client = _client()
    with caplog.at_level(logging.INFO):
        validation = client.post(
            "/validation", json={"count": "bad", "password": "plain-password"}
        )
        unknown = client.get("/unknown")
    assert validation.status_code == 400
    _assert_envelope(validation.json())
    assert "plain-password" not in str(validation.json()) + caplog.text
    assert unknown.status_code == 500
    _assert_envelope(unknown.json())
    assert unknown.json()["code"] == "INTERNAL_ERROR"
    assert "private-token" not in str(unknown.json()) + caplog.text


def test_cross_field_validation_context_is_json_safe() -> None:
    response = _client().post(
        "/cross-field-validation", json={"resource_type": "WrongRevision"}
    )
    assert response.status_code == 400
    body = response.json()
    _assert_envelope(body)
    assert body["code"] == "VALIDATION"
    assert "resource type is not supported" in str(body["details"])

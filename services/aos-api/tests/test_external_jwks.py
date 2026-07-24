"""External JWKS URL verify path — scheme 50 (no Docker required)."""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from aos_api.oidc import verify_access_token


@pytest.fixture()
def rsa_jwks_server(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    jwk = json.loads(RSAAlgorithm.to_jwk(key.public_key()))
    jwk["kid"] = "test-ext-1"
    jwk["use"] = "sig"
    jwk["alg"] = "RS256"
    jwks_body = json.dumps({"keys": [jwk]}).encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path.endswith("/certs") or self.path.endswith("/jwks"):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(jwks_body)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, *_args):  # noqa: D401
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}/realms/aos/protocol/openid-connect/certs"
    iss = "http://127.0.0.1:8083/realms/aos"
    aud = "aos-api"
    monkeypatch.setenv("AOS_OIDC_JWKS_URL", url)
    monkeypatch.setenv("AOS_OIDC_ISSUER", iss)
    monkeypatch.setenv("AOS_OIDC_AUDIENCE", aud)

    now = int(time.time())
    token = jwt.encode(
        {
            "sub": "alice",
            "iss": iss,
            "aud": aud,
            "iat": now,
            "exp": now + 600,
            "org_id": "dev-org",
            "project_id": "dev-project",
            "roles": ["developer"],
            "markings": ["public", "restricted"],
        },
        priv_pem,
        algorithm="RS256",
        headers={"kid": "test-ext-1"},
    )
    yield {"token": token, "url": url}
    server.shutdown()


def test_external_jwks_url_verifies(rsa_jwks_server):
    claims = verify_access_token(rsa_jwks_server["token"])
    assert claims["sub"] == "alice"
    assert claims["org_id"] == "dev-org"


def test_password_grant_requires_token_url(client, auth_headers):
    r = client.post(
        "/v1/auth/token",
        json={"grantType": "password", "username": "alice", "password": "x"},
    )
    assert r.status_code == 400
    assert r.json()["code"] == "UNSUPPORTED_GRANT"


def test_oidc_config_lists_grants(client):
    r = client.get("/v1/auth/oidc")
    assert r.status_code == 200
    assert "dev" in r.json()["grantTypes"]

"""JWKS URL failover — scheme 57 (no Docker required)."""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from aos_api.oidc import public_config, verify_access_token


def test_jwks_failover_uses_second_url(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    jwk = json.loads(RSAAlgorithm.to_jwk(key.public_key()))
    jwk["kid"] = "ha-1"
    jwk["use"] = "sig"
    jwk["alg"] = "RS256"
    jwks_body = json.dumps({"keys": [jwk]}).encode("utf-8")

    class GoodHandler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(jwks_body)

        def log_message(self, *_args):
            return

    class BadHandler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(503)
            self.end_headers()
            self.wfile.write(b"down")

        def log_message(self, *_args):
            return

    bad = HTTPServer(("127.0.0.1", 0), BadHandler)
    good = HTTPServer(("127.0.0.1", 0), GoodHandler)
    threading.Thread(target=bad.serve_forever, daemon=True).start()
    threading.Thread(target=good.serve_forever, daemon=True).start()
    bad_url = f"http://127.0.0.1:{bad.server_address[1]}/certs"
    good_url = f"http://127.0.0.1:{good.server_address[1]}/certs"

    iss = "http://127.0.0.1:8083/realms/aos"
    aud = "aos-api"
    monkeypatch.setenv("AOS_OIDC_JWKS_URLS", f"{bad_url},{good_url}")
    monkeypatch.delenv("AOS_OIDC_JWKS_URL", raising=False)
    monkeypatch.setenv("AOS_OIDC_ISSUER", iss)
    monkeypatch.setenv("AOS_OIDC_ISSUERS", iss)
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
            "markings": ["public"],
        },
        priv_pem,
        algorithm="RS256",
        headers={"kid": "ha-1"},
    )
    try:
        claims = verify_access_token(token)
        assert claims["sub"] == "alice"
        cfg = public_config()
        assert cfg["haMode"] is True
        assert len(cfg["jwksUrls"]) == 2
    finally:
        bad.shutdown()
        good.shutdown()

"""OpenFGA remote HTTP path — scheme 58 (mock server; no Docker)."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from aos_api.db import connect, ensure_inherit_openfga_seed, init_schema
from aos_api import openfga as fga


def test_remote_check_allowed_and_denied(monkeypatch):
    state = {"allowed_for": {"user:secret-user"}}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path.endswith("/healthz") or self.path.endswith("/stores"):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            body = json.loads(raw.decode("utf-8") or "{}")
            if self.path.endswith("/check"):
                user = (body.get("tuple_key") or {}).get("user")
                allowed = user in state["allowed_for"]
                payload = json.dumps({"allowed": allowed}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(payload)
                return
            if self.path.endswith("/read"):
                obj = (body.get("tuple_key") or {}).get("object")
                tuples = []
                if obj == "object:WorkOrder:wo-fga-demo":
                    tuples = [
                        {
                            "key": {
                                "user": "user:secret-user",
                                "relation": "viewer",
                                "object": obj,
                            }
                        }
                    ]
                payload = json.dumps({"tuples": tuples}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(payload)
                return
            if self.path.endswith("/write"):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b"{}")
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, *_args):
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    monkeypatch.setenv("AOS_OPENFGA_API_URL", base)
    monkeypatch.setenv("AOS_OPENFGA_STORE_ID", "store-test")
    monkeypatch.setenv("AOS_OPENFGA_STRICT", "0")

    assert fga.check_remote("user:secret-user", "viewer", "object:WorkOrder:wo-fga-demo") is True
    assert fga.check_remote("user:other", "viewer", "object:WorkOrder:wo-fga-demo") is False
    assert fga.has_tuples_remote("object:WorkOrder:wo-fga-demo") is True
    st = fga.status_payload()
    assert st["mode"] == "remote"
    assert st["reachable"] is True
    server.shutdown()


def test_strict_no_fallback_denies(monkeypatch):
    monkeypatch.setenv("AOS_OPENFGA_API_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("AOS_OPENFGA_STORE_ID", "x")
    monkeypatch.setenv("AOS_OPENFGA_STRICT", "1")
    init_schema()
    ensure_inherit_openfga_seed()
    with connect() as conn:
        # remote down + strict → deny even if local tuple exists
        assert (
            fga.check(conn, "user:secret-user", "viewer", "object:WorkOrder:wo-fga-demo")
            is False
        )


def test_authz_status_local(client, auth_headers, monkeypatch):
    monkeypatch.delenv("AOS_OPENFGA_API_URL", raising=False)
    r = client.get("/v1/authz/status", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["mode"] == "local"

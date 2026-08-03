#!/usr/bin/env python3
"""Transparent test proxy that replaces Bearer dev with a real harness JWT."""

from __future__ import annotations

import argparse
import http.client
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--listen-port", type=int, required=True)
    parser.add_argument("--api-port", type=int, required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    args = parser.parse_args()
    token = args.token_file.read_text().strip()
    if not token:
        raise SystemExit("empty JWT token file")

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _proxy(self) -> None:
            if self.path == "/__harness/health":
                body = b'{"status":"ok","auth":"jwt"}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length else None
            headers = {
                key: value
                for key, value in self.headers.items()
                if key.lower() not in HOP_HEADERS | {"host", "authorization"}
            }
            headers["Authorization"] = f"Bearer {token}"
            connection = http.client.HTTPConnection("127.0.0.1", args.api_port, timeout=30)
            try:
                connection.request(self.command, self.path, body=body, headers=headers)
                response = connection.getresponse()
                payload = response.read()
                self.send_response_only(response.status)
                for key, value in response.getheaders():
                    if key.lower() not in HOP_HEADERS | {"content-length"}:
                        self.send_header(key, value)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            finally:
                connection.close()

        do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = _proxy

        def log_message(self, format_string: str, *values: object) -> None:
            print(f"jwt-proxy {self.command} {self.path} " + format_string % values)

    print(json.dumps({"listenPort": args.listen_port, "apiPort": args.api_port}))
    ThreadingHTTPServer(("127.0.0.1", args.listen_port), Handler).serve_forever()


if __name__ == "__main__":
    main()

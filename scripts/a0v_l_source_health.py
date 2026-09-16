"""One-shot, metadata-only health probe for the saved QYH source."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import a0v_l_successor_business as current


API = "http://127.0.0.1:18181"
SOURCE = "niushop-qyh"
REVISION = "a84b6c79-8654-48f0-98c2-57d41b067b3d"
STATE = current.STATE / "source-health-r"
HEADERS = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "org-org",
    "X-Project-Id": "dev-project",
    "Content-Type": "application/json",
}


def _private_write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    payload = (json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n").encode()
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(payload)


def _request(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = None if body is None else json.dumps(body).encode()
    request = Request(API + path, method=method, data=data, headers=HEADERS)
    try:
        with urlopen(request, timeout=45) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        raw = error.read()
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}
        detail = payload.get("detail") if type(payload) is dict else None
        code = payload.get("code") if type(payload) is dict else None
        if code is None and type(detail) is dict:
            code = detail.get("code")
        return error.code, {"code": code if type(code) is str else "HTTP_ERROR"}


def run() -> dict:
    if (STATE / "intent.json").exists():
        raise ValueError("existing source health intent requires read-only inspection")
    health_status, health = _request("GET", "/v1/health")
    ready_status, ready = _request("GET", "/v1/ready")
    source_status, sources = _request("GET", "/v1/sources")
    matches = [row for row in sources.get("items", []) if row.get("id") == SOURCE]
    if (health_status, health, ready_status, ready) != (200, {"status": "ok"}, 200, {"status": "ready"}):
        raise ValueError("API health is not exact")
    if source_status != 200 or len(matches) != 1:
        raise ValueError("saved source is not unique")
    source = matches[0]
    if (source.get("configurationRevision") != REVISION
        or source.get("type") != "jdbc-mysql-ssh"
        or source.get("runtimeMode") != "direct"
        or source.get("status") not in {"registered", "active", "ready"}):
        raise ValueError("saved source metadata differs")
    started = datetime.now(timezone.utc).isoformat()
    _private_write(STATE / "intent.json", {
        "sourceId": SOURCE,
        "configurationRevision": REVISION,
        "probeKind": "information-schema-only",
        "maxCalls": 1,
        "startedAt": started,
    })
    status, body = _request("POST", f"/v1/sources/{SOURCE}/test", {
        "expectedConfigurationRevision": REVISION,
    })
    tables = body.get("tables") if type(body) is dict else None
    safe = {
        "outcome": "SOURCE_METADATA_HEALTH_GREEN" if status == 200 and body.get("ok") is True else "SOURCE_METADATA_HEALTH_FAILED",
        "startedAt": started,
        "finishedAt": datetime.now(timezone.utc).isoformat(),
        "httpStatus": status,
        "sourceId": SOURCE,
        "configurationRevision": REVISION,
        "latencyMs": body.get("latencyMs") if status == 200 else None,
        "tableCount": len(tables) if type(tables) is list else None,
        "tableDirectoryHash": (
            "sha256:" + sha256(json.dumps(tables, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            if type(tables) is list else None
        ),
        "truncated": body.get("truncated") if status == 200 else None,
        "errorCode": body.get("code") if status != 200 else None,
        "businessRowsRead": 0,
        "sourceCalls": 1,
    }
    _private_write(STATE / "result.json", safe)
    return safe


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))

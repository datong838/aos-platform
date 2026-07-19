"""Dev analytics-runtime sidecar (shaped) — TA.1/TA.2 · docs 110/111.

Process-isolated. Facade probes /health and proxies session tickets.
Real Notebook 7 embed lands later; this issues short-lived tickets + shaped /ui.
"""

from __future__ import annotations

import os
import secrets
import time
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

app = FastAPI(title="aos-analytics-runtime", version="0.2.0-shaped")

# in-memory sessions: id -> record
_SESSIONS: dict[str, dict[str, Any]] = {}


def _ttl_sec() -> int:
    raw = (os.environ.get("AOS_ANALYTICS_TICKET_TTL_SEC") or "900").strip()
    try:
        return max(60, min(86400, int(raw)))
    except ValueError:
        return 900


def _public_base() -> str:
    return (
        os.environ.get("AOS_ANALYTICS_PUBLIC_URL")
        or os.environ.get("AOS_ANALYTICS_URL")
        or "http://127.0.0.1:8084"
    ).rstrip("/")


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _payload() -> dict:
    return {
        "status": "ok",
        "service": "analytics-runtime",
        "engine": "shaped-dev",
        "notebookUi": "notebook7",
        "mode": "ta2-session",
        "message": "shaped Dev sidecar; ticketed /ui (not real Notebook 7)",
        "sessions": len(_SESSIONS),
    }


class SessionCreateIn(BaseModel):
    objectType: str | None = None
    datasetRid: str | None = None
    purpose: str | None = Field(default="explore")
    principal: str | None = None


@app.get("/health")
def health() -> dict:
    return _payload()


@app.get("/")
def root() -> dict:
    return {
        **_payload(),
        "paths": ["/health", "/api/status", "/v1/sessions", "/ui/{id}"],
    }


@app.get("/api/status")
def api_status() -> dict:
    return _payload()


@app.post("/v1/sessions")
def create_session(body: SessionCreateIn | None = None) -> dict[str, Any]:
    payload = body or SessionCreateIn()
    sid = f"nb-{uuid.uuid4().hex[:12]}"
    ticket = secrets.token_urlsafe(24)
    now = time.time()
    exp = now + _ttl_sec()
    base = _public_base()
    ui_url = f"{base}/ui/{sid}?ticket={quote(ticket, safe='')}"
    row: dict[str, Any] = {
        "id": sid,
        "status": "idle",
        "ticket": ticket,
        "ticketExpiresAt": _iso(exp),
        "expiresAtEpoch": exp,
        "uiUrl": ui_url,
        "objectType": payload.objectType,
        "datasetRid": payload.datasetRid,
        "purpose": payload.purpose or "explore",
        "principal": payload.principal,
        "notebookUi": "notebook7",
        "engine": "shaped-dev",
        "createdAt": _iso(now),
    }
    _SESSIONS[sid] = row
    return {
        "id": sid,
        "status": "idle",
        "uiUrl": ui_url,
        "ticket": ticket,
        "ticketExpiresAt": row["ticketExpiresAt"],
        "objectType": payload.objectType,
        "datasetRid": payload.datasetRid,
        "purpose": row["purpose"],
        "notebookUi": "notebook7",
        "engine": "shaped-dev",
        "sidecar": "ok",
    }


@app.get("/v1/sessions/{session_id}")
def get_session(session_id: str) -> dict[str, Any]:
    row = _SESSIONS.get(session_id)
    if not row:
        raise HTTPException(status_code=404, detail="session not found")
    alive = row.get("status") != "stopped" and time.time() < float(row.get("expiresAtEpoch") or 0)
    return {
        "id": row["id"],
        "status": row["status"] if alive or row.get("status") == "stopped" else "error",
        "uiUrl": row["uiUrl"],
        "ticketExpiresAt": row["ticketExpiresAt"],
        "objectType": row.get("objectType"),
        "datasetRid": row.get("datasetRid"),
        "notebookUi": "notebook7",
        "engine": "shaped-dev",
        "ticketValid": alive and bool(row.get("ticket")),
    }


@app.delete("/v1/sessions/{session_id}")
def delete_session(session_id: str) -> dict[str, Any]:
    row = _SESSIONS.get(session_id)
    if not row:
        raise HTTPException(status_code=404, detail="session not found")
    row["status"] = "stopped"
    row["ticket"] = None
    row["stoppedAt"] = _iso(time.time())
    return {
        "id": session_id,
        "status": "stopped",
        "ticketExpiresAt": row.get("ticketExpiresAt"),
        "notebookUi": "notebook7",
        "engine": "shaped-dev",
    }


@app.get("/ui/{session_id}", response_class=HTMLResponse)
def notebook_ui(session_id: str, ticket: str = Query(default="")) -> HTMLResponse:
    row = _SESSIONS.get(session_id)
    if not row or row.get("status") == "stopped":
        raise HTTPException(status_code=404, detail="session not found")
    if not ticket or ticket != row.get("ticket"):
        raise HTTPException(status_code=403, detail="invalid or missing ticket")
    if time.time() >= float(row.get("expiresAtEpoch") or 0):
        raise HTTPException(status_code=403, detail="ticket expired")
    ot = row.get("objectType") or "—"
    ds = row.get("datasetRid") or "—"
    html = f"""<!doctype html>
<html lang="zh-CN"><head>
<meta charset="utf-8"/>
<title>AOS Analytics · shaped</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem; background: #0f1419; color: #e7ecf1; }}
  .box {{ max-width: 40rem; border: 1px solid #2a3540; padding: 1.25rem 1.5rem; }}
  .muted {{ color: #8b9aab; font-size: 0.875rem; }}
  code {{ color: #7dd3c0; }}
</style>
</head><body>
<div class="box">
  <h1 style="margin:0 0 0.5rem;font-size:1.25rem">Notebook 7 · shaped Dev</h1>
  <p class="muted">TA.2 ticketed UI · engine=shaped-dev · not a real Jupyter kernel</p>
  <p>session=<code>{session_id}</code></p>
  <p>status=<code>idle</code> · objectType=<code>{ot}</code> · dataset=<code>{ds}</code></p>
  <p class="muted">Write-back must go via AIP Drafts (no analyst self-approve).</p>
</div>
</body></html>"""
    return HTMLResponse(content=html)

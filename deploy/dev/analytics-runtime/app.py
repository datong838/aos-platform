"""Dev analytics-runtime sidecar — TA.1/TA.2 + 157 true Jupyter MVP.

Modes (AOS_ANALYTICS_ENGINE):
  · jupyter — Jupyter Server + Notebook 7 + ipykernel; ticketed /ui → 302
  · shaped  — HTML stub (TA.2 fallback; no kernel)

Facade probes /health and proxies session tickets. UI never receives Jupyter
token in session JSON; token only appears after ticket validation redirect.
"""

from __future__ import annotations

import json
import os
import secrets
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    if _engine() == "jupyter":
        _start_jupyter()
    try:
        yield
    finally:
        _stop_jupyter()


app = FastAPI(
    title="aos-analytics-runtime",
    version="0.3.0-jupyter-mvp",
    lifespan=_lifespan,
)

_SESSIONS: dict[str, dict[str, Any]] = {}
_JUPYTER_PROC: subprocess.Popen[bytes] | None = None
_JUPYTER_TOKEN: str = ""
_JUPYTER_READY = False


def _engine() -> str:
    raw = (os.environ.get("AOS_ANALYTICS_ENGINE") or "shaped").strip().lower()
    if raw in {"jupyter", "jupyter-server", "notebook7", "nb7"}:
        return "jupyter"
    return "shaped"


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


def _jupyter_public() -> str:
    return (
        os.environ.get("AOS_JUPYTER_PUBLIC_URL") or "http://127.0.0.1:8888"
    ).rstrip("/")


def _jupyter_port() -> int:
    raw = (os.environ.get("AOS_JUPYTER_PORT") or "8888").strip()
    try:
        return max(1024, min(65535, int(raw)))
    except ValueError:
        return 8888


def _notebook_root() -> Path:
    raw = (os.environ.get("AOS_JUPYTER_ROOT") or "").strip()
    if raw:
        p = Path(raw)
    else:
        p = Path(__file__).resolve().parent / "notebooks"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_smoke_notebook(root: Path) -> Path:
    path = root / "aos_smoke.ipynb"
    if path.is_file():
        return path
    nb = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python"},
        },
        "cells": [
            {
                "id": "aos-md-1",
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "# AOS analytics smoke\n",
                    "真 Jupyter MVP（方案 157）· 写回须走 AIP Draft，禁止自批。\n",
                ],
            },
            {
                "id": "aos-code-1",
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": ["print(1 + 1)\n"],
            },
        ],
    }
    path.write_text(json.dumps(nb, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _jupyter_available() -> bool:
    try:
        import notebook  # noqa: F401
        import jupyter_server  # noqa: F401
    except ImportError:
        return False
    return True


def _start_jupyter() -> None:
    global _JUPYTER_PROC, _JUPYTER_TOKEN, _JUPYTER_READY
    if _JUPYTER_PROC is not None and _JUPYTER_PROC.poll() is None:
        _JUPYTER_READY = True
        return
    if not _jupyter_available():
        _JUPYTER_READY = False
        return

    root = _notebook_root()
    _ensure_smoke_notebook(root)
    _JUPYTER_TOKEN = (os.environ.get("AOS_JUPYTER_TOKEN") or "").strip() or secrets.token_urlsafe(24)
    port = _jupyter_port()
    # Prefer `jupyter notebook` (Notebook 7); fall back to module.
    cmd = [
        sys.executable,
        "-m",
        "jupyter",
        "notebook",
        f"--ip=0.0.0.0",
        f"--port={port}",
        "--no-browser",
        "--allow-root",
        f"--NotebookApp.token={_JUPYTER_TOKEN}",
        "--NotebookApp.password=",
        f"--NotebookApp.notebook_dir={str(root)}",
        "--NotebookApp.allow_origin=*",
        "--NotebookApp.disable_check_xsrf=True",
    ]
    env = os.environ.copy()
    env["JUPYTER_TOKEN"] = _JUPYTER_TOKEN
    _JUPYTER_PROC = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        start_new_session=True,
    )
    # wait briefly for bind
    deadline = time.time() + 20
    import socket

    while time.time() < deadline:
        if _JUPYTER_PROC.poll() is not None:
            _JUPYTER_READY = False
            return
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            try:
                s.connect(("127.0.0.1", port))
                _JUPYTER_READY = True
                return
            except OSError:
                time.sleep(0.25)
    _JUPYTER_READY = False


def _stop_jupyter() -> None:
    global _JUPYTER_PROC, _JUPYTER_READY
    proc = _JUPYTER_PROC
    _JUPYTER_PROC = None
    _JUPYTER_READY = False
    if not proc:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.terminate()
        except Exception:
            pass
    try:
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _payload() -> dict:
    eng = _engine()
    if eng == "jupyter":
        ready = _JUPYTER_READY and _jupyter_available()
        return {
            "status": "ok" if ready else "degraded",
            "service": "analytics-runtime",
            "engine": "jupyter-server" if ready else "jupyter-pending",
            "notebookUi": "notebook7",
            "mode": "ta2-session+jupyter-mvp",
            "message": (
                "true Jupyter Notebook 7 + ticketed /ui redirect (scheme 157)"
                if ready
                else "jupyter mode requested but server not ready (packages or bind)"
            ),
            "sessions": len(_SESSIONS),
            "jupyterPort": _jupyter_port(),
            "jupyterReady": ready,
        }
    return {
        "status": "ok",
        "service": "analytics-runtime",
        "engine": "shaped-dev",
        "notebookUi": "notebook7",
        "mode": "ta2-session",
        "message": "shaped Dev sidecar; ticketed /ui (not real Notebook 7)",
        "sessions": len(_SESSIONS),
    }


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


def _session_engine_label() -> str:
    p = _payload()
    return str(p.get("engine") or "shaped-dev")


class SessionCreateIn(BaseModel):
    objectType: str | None = None
    datasetRid: str | None = None
    purpose: str | None = Field(default="explore")
    principal: str | None = None


@app.post("/v1/sessions")
def create_session(body: SessionCreateIn | None = None) -> dict[str, Any]:
    payload = body or SessionCreateIn()
    sid = f"nb-{uuid.uuid4().hex[:12]}"
    ticket = secrets.token_urlsafe(24)
    now = time.time()
    exp = now + _ttl_sec()
    base = _public_base()
    ui_url = f"{base}/ui/{sid}?ticket={quote(ticket, safe='')}"
    notebook_name = f"{sid}.ipynb"
    if _engine() == "jupyter":
        root = _notebook_root()
        _ensure_smoke_notebook(root)
        # per-session copy of smoke so users don't collide
        src = root / "aos_smoke.ipynb"
        dst = root / notebook_name
        if src.is_file() and not dst.is_file():
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    eng = _session_engine_label()
    row: dict[str, Any] = {
        "id": sid,
        "status": "idle" if eng.startswith("jupyter") else "idle",
        "ticket": ticket,
        "ticketExpiresAt": _iso(exp),
        "expiresAtEpoch": exp,
        "uiUrl": ui_url,
        "objectType": payload.objectType,
        "datasetRid": payload.datasetRid,
        "purpose": payload.purpose or "explore",
        "principal": payload.principal,
        "notebookUi": "notebook7",
        "engine": eng,
        "notebookFile": notebook_name,
        "createdAt": _iso(now),
    }
    _SESSIONS[sid] = row
    return {
        "id": sid,
        "status": row["status"],
        "uiUrl": ui_url,
        "ticket": ticket,
        "ticketExpiresAt": row["ticketExpiresAt"],
        "objectType": payload.objectType,
        "datasetRid": payload.datasetRid,
        "purpose": row["purpose"],
        "notebookUi": "notebook7",
        "engine": eng,
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
        "engine": row.get("engine") or _session_engine_label(),
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
        "engine": row.get("engine") or _session_engine_label(),
    }


def _assert_ticket(session_id: str, ticket: str) -> dict[str, Any]:
    row = _SESSIONS.get(session_id)
    if not row or row.get("status") == "stopped":
        raise HTTPException(status_code=404, detail="session not found")
    if not ticket or ticket != row.get("ticket"):
        raise HTTPException(status_code=403, detail="invalid or missing ticket")
    if time.time() >= float(row.get("expiresAtEpoch") or 0):
        raise HTTPException(status_code=403, detail="ticket expired")
    return row


@app.get("/ui/{session_id}")
def notebook_ui(session_id: str, ticket: str = Query(default="")):
    row = _assert_ticket(session_id, ticket)

    if _engine() == "jupyter" and _JUPYTER_READY and _JUPYTER_TOKEN:
        nb_file = row.get("notebookFile") or "aos_smoke.ipynb"
        # Notebook 7 classic path
        q = urlencode({"token": _JUPYTER_TOKEN})
        target = f"{_jupyter_public()}/notebooks/{quote(str(nb_file))}?{q}"
        row["status"] = "running"
        return RedirectResponse(url=target, status_code=302)

    # shaped fallback HTML
    ot = row.get("objectType") or "—"
    ds = row.get("datasetRid") or "—"
    eng = row.get("engine") or "shaped-dev"
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
  <h1 style="margin:0 0 0.5rem;font-size:1.25rem">Notebook 7 · shaped fallback</h1>
  <p class="muted">ticket ok · engine=<code>{eng}</code> · Jupyter not ready — set AOS_ANALYTICS_ENGINE=jupyter and install notebook</p>
  <p>session=<code>{session_id}</code></p>
  <p>objectType=<code>{ot}</code> · dataset=<code>{ds}</code></p>
  <p class="muted">Write-back must go via AIP Drafts (no analyst self-approve).</p>
</div>
</body></html>"""
    return HTMLResponse(content=html)

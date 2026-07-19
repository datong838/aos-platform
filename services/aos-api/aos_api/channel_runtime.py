"""Notification channel store + runtime — scheme 101."""
from __future__ import annotations

import json
import os
import smtplib
import uuid
from email.message import EmailMessage
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

from aos_api.aip_kv_store import get_payload, put_payload
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.channel_runtime")

KEY_WEBHOOKS = "channel_webhooks"
KEY_OUTBOX = "channel_outbox"


def _load_webhooks() -> list[dict[str, Any]]:
    stored = get_payload(KEY_WEBHOOKS) or {}
    raw = stored.get("items")
    return list(raw) if isinstance(raw, list) else []


def _save_webhooks(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    put_payload(KEY_WEBHOOKS, {"items": items})
    return items


def list_webhooks() -> list[dict[str, Any]]:
    return _load_webhooks()


def register_webhook(*, url: str, event: str, **extra: Any) -> dict[str, Any]:
    items = _load_webhooks()
    item = {
        "id": f"wh-{uuid.uuid4().hex[:8]}",
        "url": url,
        "event": event,
        "status": "registered",
        "pluginId": "channel-webhook",
        **{k: v for k, v in extra.items() if v is not None},
    }
    items.append(item)
    _save_webhooks(items)
    log.info("webhook_registered id=%s event=%s", item["id"], event)
    return item


def _append_outbox(row: dict[str, Any]) -> dict[str, Any]:
    stored = get_payload(KEY_OUTBOX) or {}
    items = list(stored.get("items") or []) if isinstance(stored.get("items"), list) else []
    items.append(row)
    # keep last 200
    put_payload(KEY_OUTBOX, {"items": items[-200:]})
    return row


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def smtp_configured() -> bool:
    return bool(_env("AOS_SMTP_HOST"))


def _send_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    hooks = _load_webhooks()
    event = str(payload.get("event") or "")
    matched = [h for h in hooks if not event or h.get("event") == event] or hooks
    deliveries: list[dict[str, Any]] = []
    for h in matched:
        url = str(h.get("url") or "")
        entry: dict[str, Any] = {"webhookId": h.get("id"), "url": url, "ok": False}
        if not url:
            entry["error"] = "empty url"
            deliveries.append(entry)
            continue
        dry = _env("AOS_WEBHOOK_DRY_RUN", "1").lower() in {"1", "true", "yes"}
        if dry:
            entry["ok"] = True
            entry["mode"] = "dry-run"
            deliveries.append(entry)
            continue
        try:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urlrequest.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlrequest.urlopen(req, timeout=5) as resp:
                entry["ok"] = 200 <= int(resp.status) < 300
                entry["status"] = int(resp.status)
                entry["mode"] = "http"
        except (urlerror.URLError, TimeoutError, ValueError) as exc:
            entry["error"] = str(exc)
            entry["mode"] = "http"
        deliveries.append(entry)
    out = {
        "ok": any(d.get("ok") for d in deliveries) if deliveries else True,
        "pluginId": "channel-webhook",
        "deliveries": deliveries,
        "matched": len(matched),
    }
    _append_outbox({"id": f"ob-{uuid.uuid4().hex[:8]}", "channel": "channel-webhook", **out})
    return out


def _send_email(payload: dict[str, Any]) -> dict[str, Any]:
    if not smtp_configured():
        raise ApiError(
            code="CHANNEL_STUB",
            message="channel-email requires AOS_SMTP_HOST (and related env); not configured",
            status_code=501,
            details={"pluginId": "channel-email", "hint": "set AOS_SMTP_HOST/PORT/USER/PASSWORD/FROM"},
        )
    to = str(payload.get("to") or payload.get("recipient") or "").strip()
    subject = str(payload.get("subject") or "(no subject)")
    body = str(payload.get("body") or payload.get("text") or "")
    if not to:
        raise ApiError(code="VALIDATION", message="email.to required", status_code=400)
    host = _env("AOS_SMTP_HOST")
    port = int(_env("AOS_SMTP_PORT", "587") or "587")
    user = _env("AOS_SMTP_USER")
    password = _env("AOS_SMTP_PASSWORD")
    mail_from = _env("AOS_SMTP_FROM") or user or "aos@localhost"
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = to
    msg.set_content(body)
    with smtplib.SMTP(host, port, timeout=10) as smtp:
        smtp.ehlo()
        if _env("AOS_SMTP_STARTTLS", "1").lower() in {"1", "true", "yes"}:
            try:
                smtp.starttls()
                smtp.ehlo()
            except smtplib.SMTPException:
                pass
        if user:
            smtp.login(user, password)
        smtp.send_message(msg)
    out = {
        "ok": True,
        "pluginId": "channel-email",
        "mode": "smtp",
        "to": to,
        "subject": subject,
    }
    _append_outbox({"id": f"ob-{uuid.uuid4().hex[:8]}", "channel": "channel-email", **out})
    return out


def _send_sms(payload: dict[str, Any]) -> dict[str, Any]:
    _ = payload
    raise ApiError(
        code="CHANNEL_STUB",
        message="channel-sms has no live provider configured",
        status_code=501,
        details={"pluginId": "channel-sms"},
    )


_HANDLERS = {
    "channel-webhook": _send_webhook,
    "channel-email": _send_email,
    "channel-sms": _send_sms,
}


def assert_installed(plugin_id: str) -> str:
    from aos_api.channel_registry import list_channel_plugins

    body = list_channel_plugins()
    hit = next((i for i in body.get("items") or [] if i.get("id") == plugin_id), None)
    if not hit:
        raise ApiError(code="UNKNOWN_CHANNEL", message=f"unknown channel plugin: {plugin_id}", status_code=400)
    if not hit.get("installed"):
        raise ApiError(
            code="PLUGIN_NOT_INSTALLED",
            message=f"channel plugin not installed: {plugin_id}",
            status_code=400,
        )
    return plugin_id


def dispatch_send(plugin_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    pid = assert_installed((plugin_id or "").strip())
    handler = _HANDLERS.get(pid)
    if not handler:
        raise ApiError(
            code="CHANNEL_STUB",
            message=f"no send handler for {pid}",
            status_code=501,
            details={"pluginId": pid},
        )
    return handler(payload or {})


def channel_health(plugin_id: str) -> dict[str, Any]:
    pid = assert_installed((plugin_id or "").strip())
    if pid == "channel-webhook":
        return {
            "ok": True,
            "pluginId": pid,
            "registered": len(_load_webhooks()),
            "dryRunDefault": _env("AOS_WEBHOOK_DRY_RUN", "1"),
        }
    if pid == "channel-email":
        return {
            "ok": smtp_configured(),
            "pluginId": pid,
            "smtpConfigured": smtp_configured(),
            "mode": "smtp" if smtp_configured() else "stub",
        }
    return {"ok": False, "pluginId": pid, "mode": "stub"}

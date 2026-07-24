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


def delete_webhook(webhook_id: str) -> bool:
    """209m — unregister webhook by id."""
    wid = (webhook_id or "").strip()
    items = _load_webhooks()
    nxt = [h for h in items if str(h.get("id")) != wid]
    if len(nxt) == len(items):
        return False
    _save_webhooks(nxt)
    log.info("webhook_deleted id=%s", wid)
    return True


def _webhook_signature_headers(body: bytes) -> dict[str, str]:
    """209m — optional HMAC-SHA256 when AOS_WEBHOOK_SIGNING_SECRET set."""
    import hashlib
    import hmac

    secret = _env("AOS_WEBHOOK_SIGNING_SECRET")
    if not secret:
        return {}
    dig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return {"X-AOS-Signature": f"sha256={dig}"}


def _append_outbox(row: dict[str, Any]) -> dict[str, Any]:
    stored = get_payload(KEY_OUTBOX) or {}
    items = list(stored.get("items") or []) if isinstance(stored.get("items"), list) else []
    items.append(row)
    # keep last 200
    put_payload(KEY_OUTBOX, {"items": items[-200:]})
    return row


def list_outbox(*, limit: int = 50) -> list[dict[str, Any]]:
    """212m — recent channel deliveries."""
    stored = get_payload(KEY_OUTBOX) or {}
    items = list(stored.get("items") or []) if isinstance(stored.get("items"), list) else []
    lim = max(1, min(int(limit or 50), 200))
    return list(reversed(items[-lim:]))


def _save_outbox(items: list[dict[str, Any]]) -> None:
    put_payload(KEY_OUTBOX, {"items": items[-200:]})


def retry_outbox(outbox_id: str) -> dict[str, Any]:
    """212m — re-dispatch using stored payload."""
    oid = (outbox_id or "").strip()
    stored = get_payload(KEY_OUTBOX) or {}
    items = list(stored.get("items") or []) if isinstance(stored.get("items"), list) else []
    hit = next((i for i in items if str(i.get("id")) == oid), None)
    if not hit:
        raise ApiError(code="NOT_FOUND", message="outbox item not found", status_code=404)
    channel = str(hit.get("channel") or hit.get("pluginId") or "").strip()
    payload = hit.get("payload")
    if not isinstance(payload, dict):
        raise ApiError(
            code="OUTBOX_NO_PAYLOAD",
            message="outbox item has no payload to retry (pre-212m entry)",
            status_code=400,
        )
    if not channel:
        raise ApiError(code="VALIDATION", message="outbox channel missing", status_code=400)
    result = dispatch_send(channel, payload)
    # reload after dispatch (which appends a new outbox row)
    stored2 = get_payload(KEY_OUTBOX) or {}
    items2 = list(stored2.get("items") or []) if isinstance(stored2.get("items"), list) else []
    for row in items2:
        if str(row.get("id")) == oid:
            row["status"] = "retried"
            break
    _save_outbox(items2)
    return {"ok": True, "retriedId": oid, "result": result}


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
            headers = {
                "Content-Type": "application/json",
                **_webhook_signature_headers(data),
            }
            if "X-AOS-Signature" in headers:
                entry["signed"] = True
            req = urlrequest.Request(
                url,
                data=data,
                headers=headers,
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
    _append_outbox(
        {
            "id": f"ob-{uuid.uuid4().hex[:8]}",
            "channel": "channel-webhook",
            "payload": payload,
            **out,
        }
    )
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
    _append_outbox(
        {
            "id": f"ob-{uuid.uuid4().hex[:8]}",
            "channel": "channel-email",
            "payload": payload,
            **out,
        }
    )
    return out


def _send_sms(payload: dict[str, Any]) -> dict[str, Any]:
    """198m — optional HTTP/Webhook SMS; unconfigured → 501."""
    if not sms_configured():
        raise ApiError(
            code="CHANNEL_STUB",
            message="channel-sms requires AOS_SMS_WEBHOOK_URL or AOS_SMS_API_URL+AOS_SMS_API_KEY",
            status_code=501,
            details={"pluginId": "channel-sms"},
        )
    to = str(payload.get("to") or payload.get("phone") or payload.get("recipient") or "").strip()
    body = str(payload.get("body") or payload.get("text") or payload.get("message") or "")
    if not to:
        raise ApiError(code="VALIDATION", message="sms.to required", status_code=400)
    webhook = _env("AOS_SMS_WEBHOOK_URL")
    api_url = _env("AOS_SMS_API_URL")
    api_key = _env("AOS_SMS_API_KEY")
    url = webhook or api_url
    headers = {"Content-Type": "application/json"}
    if api_key and not webhook:
        headers["Authorization"] = f"Bearer {api_key}"
    data = json.dumps({"to": to, "body": body}, ensure_ascii=False).encode("utf-8")
    req = urlrequest.Request(url, data=data, headers=headers, method="POST")
    try:
        with urlrequest.urlopen(req, timeout=10) as resp:
            status = int(resp.status)
            if not (200 <= status < 300):
                raise ApiError(
                    code="CHANNEL_UPSTREAM",
                    message=f"sms upstream HTTP {status}",
                    status_code=502,
                )
    except ApiError:
        raise
    except (urlerror.URLError, TimeoutError, ValueError) as exc:
        raise ApiError(
            code="CHANNEL_UPSTREAM",
            message=f"sms upstream failed: {exc}",
            status_code=502,
        ) from None
    out = {
        "ok": True,
        "pluginId": "channel-sms",
        "mode": "http",
        "to": to,
    }
    _append_outbox(
        {
            "id": f"ob-{uuid.uuid4().hex[:8]}",
            "channel": "channel-sms",
            "payload": payload,
            **out,
        }
    )
    return out


def sms_configured() -> bool:
    if _env("AOS_SMS_WEBHOOK_URL"):
        return True
    return bool(_env("AOS_SMS_API_URL") and _env("AOS_SMS_API_KEY"))


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
    if pid == "channel-sms":
        return {
            "ok": sms_configured(),
            "pluginId": pid,
            "smsConfigured": sms_configured(),
            "mode": "http" if sms_configured() else "stub",
        }
    return {"ok": False, "pluginId": pid, "mode": "stub"}

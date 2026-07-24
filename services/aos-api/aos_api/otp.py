"""182m — email/phone OTP for member add / profile contact change."""
from __future__ import annotations

import hashlib
import os
import secrets
import time
import uuid
from typing import Any

from aos_api.logging_facade import get_logger

log = get_logger("aos-api.otp")

# otpId -> record (memory; also PG when twa_pg enabled)
_OTP: dict[str, dict[str, Any]] = {}
# ticket -> {purpose, destination, channel, exp}
_TICKETS: dict[str, dict[str, Any]] = {}


def reset_otp_store() -> None:
    _OTP.clear()
    _TICKETS.clear()


def otp_required() -> bool:
    return (os.getenv("AOS_OTP_REQUIRED") or "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _dev_code() -> str:
    return (os.getenv("AOS_OTP_DEV_CODE") or "123456").strip() or "123456"


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def send_otp(
    *,
    channel: str,
    to: str,
    purpose: str,
) -> dict[str, Any]:
    ch = (channel or "").strip().lower()
    if ch not in {"email", "phone"}:
        raise ValueError("channel must be email or phone")
    dest = (to or "").strip()
    if not dest:
        raise ValueError("to required")
    if ch == "email":
        from aos_api.person_identity import normalize_email

        dest = normalize_email(dest)
    else:
        from aos_api.person_identity import normalize_phone

        dest = normalize_phone(dest)
    pur = (purpose or "").strip() or "invite"
    if pur not in {"invite", "profile"}:
        raise ValueError("purpose must be invite or profile")

    # Delivery: Dev fixed/logged code; optional SMTP for email
    code = _dev_code()
    delivered = "dev"
    if ch == "email":
        try:
            from aos_api.channel_runtime import smtp_configured

            if smtp_configured() and (os.getenv("AOS_OTP_FORCE_DEV") or "").lower() not in {
                "1",
                "true",
                "yes",
            }:
                code = f"{secrets.randbelow(10**6):06d}"
                from aos_api.channel_runtime import _send_email  # noqa: PLC2701

                _send_email(
                    {
                        "to": dest,
                        "subject": "AOS 验证码",
                        "body": f"您的验证码是 {code}，10 分钟内有效。",
                    }
                )
                delivered = "smtp"
        except Exception as exc:
            log.warning("otp_email_send_fallback_dev err=%s", exc)
            code = _dev_code()
            delivered = "dev"
    else:
        delivered = "dev"
        log.info("otp_sms_dev_only to=%s (no SMS provider)", dest)

    otp_id = f"otp-{uuid.uuid4().hex[:12]}"
    expires_in = 600
    expires_ts = time.time() + expires_in
    row = {
        "id": otp_id,
        "channel": ch,
        "destination": dest,
        "purpose": pur,
        "code_hash": _hash_code(code),
        "expires_ts": expires_ts,
        "consumed": False,
    }
    _OTP[otp_id] = row
    try:
        from aos_api import twa_pg

        twa_pg.otp_insert(
            otp_id=otp_id,
            channel=ch,
            destination=dest,
            purpose=pur,
            code_hash=row["code_hash"],
            expires_ts=expires_ts,
        )
    except Exception:
        pass
    log.info(
        "otp_send id=%s channel=%s purpose=%s delivered=%s code_dev=%s",
        otp_id,
        ch,
        pur,
        delivered,
        code if delivered == "dev" else "(hidden)",
    )
    out: dict[str, Any] = {
        "otpId": otp_id,
        "expiresIn": expires_in,
        "channel": ch,
        "delivered": delivered,
    }
    if delivered == "dev":
        out["devCode"] = code  # only in Dev delivery
    return out


def verify_otp(*, otp_id: str, code: str) -> dict[str, Any]:
    oid = (otp_id or "").strip()
    row = _OTP.get(oid)
    if row is None:
        try:
            from aos_api import twa_pg

            prow = twa_pg.otp_get(oid)
            if prow:
                row = {
                    "id": prow["id"],
                    "channel": prow["channel"],
                    "destination": prow["destination"],
                    "purpose": prow["purpose"],
                    "code_hash": prow["code_hash"],
                    "expires_ts": float(prow["expires_ts"]),
                    "consumed": bool(prow["consumed"]),
                }
                _OTP[oid] = row
        except Exception:
            row = None
    if not row:
        raise LookupError("otp not found")
    if row.get("consumed"):
        raise ValueError("otp already used")
    if time.time() > float(row["expires_ts"]):
        raise ValueError("otp expired")
    if _hash_code((code or "").strip()) != row["code_hash"]:
        raise ValueError("invalid code")
    row["consumed"] = True
    try:
        from aos_api import twa_pg

        twa_pg.otp_consume(oid)
    except Exception:
        pass
    ticket = f"tkt-{uuid.uuid4().hex[:16]}"
    _TICKETS[ticket] = {
        "purpose": row["purpose"],
        "channel": row["channel"],
        "destination": row["destination"],
        "expires_ts": time.time() + 300,
    }
    log.info("otp_verify_ok id=%s ticket=%s", oid, ticket)
    return {"ok": True, "ticket": ticket, "expiresIn": 300}


def consume_ticket(
    ticket: str,
    *,
    purpose: str,
    channel: str | None = None,
    destination: str | None = None,
) -> bool:
    """Consume one-time ticket. Returns True if valid."""
    if not otp_required():
        return True
    t = (ticket or "").strip()
    row = _TICKETS.pop(t, None)
    if not row:
        return False
    if time.time() > float(row["expires_ts"]):
        return False
    if row["purpose"] != purpose:
        return False
    if channel and row["channel"] != channel:
        return False
    if destination and row["destination"] != destination:
        return False
    return True


def require_ticket_for_contact(
    *,
    ticket: str | None,
    email: str | None,
    phone: str | None,
    purpose: str,
) -> None:
    """Raise ValueError if OTP required and ticket missing/invalid for email/phone write."""
    if not otp_required():
        return
    if not (email or phone):
        return  # subject-only add — no OTP
    ch = "email" if email else "phone"
    if email:
        from aos_api.person_identity import normalize_email

        dest = normalize_email(email)
    else:
        from aos_api.person_identity import normalize_phone

        dest = normalize_phone(phone or "")
    if not consume_ticket(ticket or "", purpose=purpose, channel=ch, destination=dest):
        raise ValueError("otp ticket required or invalid for contact verification")

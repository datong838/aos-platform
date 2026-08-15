"""Shared fail-closed redaction for ecommerce object projections."""

from __future__ import annotations

from typing import Any


_ECOM_PII_FIELDS = frozenset(
    {
        "mobile",
        "telephone",
        "phone",
        "weapp_openid",
        "wx_openid",
        "openid",
        "email",
        "pay_password",
        "password",
        "mobile_country_code",
        "buyer_ip",
        "last_login_ip",
        "reg_ip",
        "id_card",
        "id_card_no",
        "bank_card",
        "bank_account",
        "real_name",
    }
)
_ECOM_PII_PREFIXES = ("mobile", "phone", "tel", "openid", "password", "email")


def redact_ecommerce_pii(payload: dict[str, Any]) -> dict[str, Any]:
    """Mask known customer identifiers after marking-based redaction."""
    if not isinstance(payload, dict):
        return payload
    out = dict(payload)
    redacted = set(out.get("_redactedFields", []))
    for key in list(out):
        lowered = key.lower()
        is_pii = lowered in _ECOM_PII_FIELDS or any(
            lowered.startswith(prefix) for prefix in _ECOM_PII_PREFIXES
        )
        if is_pii and lowered != "telephone":
            out[key] = "[REDACTED]"
            redacted.add(key)
    if redacted:
        out["_redactedFields"] = sorted(redacted)
    return out


__all__ = ["redact_ecommerce_pii"]

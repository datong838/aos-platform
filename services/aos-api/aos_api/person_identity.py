"""TWA.12 / 168 — normalize email/phone to canonical membership subject."""
from __future__ import annotations

import re
from typing import Any

from aos_api.logging_facade import get_logger

log = get_logger("aos-api.person-identity")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_DIGITS = re.compile(r"[^\d+]")

# subject -> profile
_PERSONS: dict[str, dict[str, Any]] = {}


def reset_person_store() -> None:
    _PERSONS.clear()


def upsert_person_profile(
    subject: str,
    *,
    email: str | None = None,
    phone: str | None = None,
    display_name: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    sub = (subject or "").strip()
    if not sub:
        raise ValueError("subject required")
    prev = dict(_PERSONS.get(sub, {}))
    if email:
        prev["email"] = normalize_email(email)
    if phone:
        prev["phone"] = normalize_phone(phone)
    if display_name:
        prev["displayName"] = display_name.strip()
    if title:
        prev["title"] = title.strip()
    prev["subject"] = sub
    _PERSONS[sub] = prev
    return dict(prev)


def seed_dev_persons() -> None:
    """Bind human profiles to Dev seed subjects (alice / user:dev / bob)."""
    upsert_person_profile(
        "alice",
        email="alice@acme.example",
        phone="+8613800138000",
        display_name="艾丽斯",
        title="组织所有者",
    )
    upsert_person_profile(
        "user:dev",
        email="dev@local.aos",
        phone="+8613900139000",
        display_name="本机开发者",
        title="本机 Bearer 登录账号",
    )
    upsert_person_profile(
        "bob",
        email="bob@acme.example",
        phone="+8613700137000",
        display_name="鲍勃",
        title="运营查看者",
    )


def normalize_email(raw: str) -> str:
    addr = (raw or "").strip().lower()
    if not addr or not _EMAIL_RE.match(addr):
        raise ValueError("invalid email")
    return addr


def normalize_phone(raw: str) -> str:
    s = _PHONE_DIGITS.sub("", (raw or "").strip())
    if not s:
        raise ValueError("invalid phone")
    if s.startswith("00"):
        s = "+" + s[2:]
    if s.isdigit() and len(s) == 11 and s.startswith("1"):
        s = "+86" + s
    if s.isdigit() and not s.startswith("+"):
        s = "+" + s
    if not s.startswith("+") or len(re.sub(r"\D", "", s)) < 8:
        raise ValueError("invalid phone")
    return s


def subject_from_email(email: str) -> str:
    return f"email:{normalize_email(email)}"


def subject_from_phone(phone: str) -> str:
    return f"phone:{normalize_phone(phone)}"


def resolve_member_identity(
    *,
    subject: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    display_name: str | None = None,
) -> dict[str, Any]:
    """Prefer email > phone > subject. Returns canonical subject + profile fields."""
    sub = (subject or "").strip()
    em = (email or "").strip()
    ph = (phone or "").strip()
    if em:
        canon = subject_from_email(em)
        profile = {
            "subject": canon,
            "email": normalize_email(em),
            "phone": _PERSONS.get(canon, {}).get("phone"),
            "displayName": (display_name or "").strip() or normalize_email(em),
            "kind": "email",
        }
    elif ph:
        canon = subject_from_phone(ph)
        e164 = normalize_phone(ph)
        profile = {
            "subject": canon,
            "email": _PERSONS.get(canon, {}).get("email"),
            "phone": e164,
            "displayName": (display_name or "").strip() or e164,
            "kind": "phone",
        }
    elif sub:
        existing = _PERSONS.get(sub, {})
        profile = {
            "subject": sub,
            "email": existing.get("email"),
            "phone": existing.get("phone"),
            "displayName": (display_name or "").strip()
            or existing.get("displayName")
            or sub,
            "kind": "subject",
        }
    else:
        raise ValueError("email, phone, or subject required")

    prev = _PERSONS.get(profile["subject"], {})
    merged = {**prev, **{k: v for k, v in profile.items() if v}}
    _PERSONS[profile["subject"]] = merged
    log.info(
        "person_resolve subject=%s kind=%s",
        profile["subject"],
        profile["kind"],
    )
    return merged


def get_profile(subject: str) -> dict[str, Any]:
    sub = (subject or "").strip()
    prof = dict(_PERSONS.get(sub, {}))
    if not prof:
        return {
            "subject": sub,
            "displayName": sub,
            "displayLabel": sub,
            "email": None,
            "phone": None,
            "title": None,
        }
    out = {
        "subject": sub,
        "displayName": prof.get("displayName") or sub,
        "displayLabel": prof.get("displayName")
        or prof.get("email")
        or prof.get("phone")
        or sub,
        "email": prof.get("email"),
        "phone": prof.get("phone"),
        "title": prof.get("title"),
    }
    return out


def update_own_profile(
    subject: str,
    *,
    display_name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    """Update profile for login subject. Does NOT change membership subject key."""
    sub = (subject or "").strip()
    if not sub:
        raise ValueError("subject required")
    prev = dict(_PERSONS.get(sub, {"subject": sub}))
    if display_name is not None:
        prev["displayName"] = display_name.strip() or sub
    if title is not None:
        t = title.strip()
        if t:
            prev["title"] = t
        else:
            prev.pop("title", None)
    if email is not None:
        if email.strip() == "":
            prev.pop("email", None)
        else:
            prev["email"] = normalize_email(email)
    if phone is not None:
        if phone.strip() == "":
            prev.pop("phone", None)
        else:
            prev["phone"] = normalize_phone(phone)
    prev["subject"] = sub
    _PERSONS[sub] = prev
    log.info("person_profile_update subject=%s", sub)
    return get_profile(sub)


def enrich_member_row(row: dict[str, Any]) -> dict[str, Any]:
    sub = row.get("subject") or ""
    prof = _PERSONS.get(sub, {})
    out = dict(row)
    if prof.get("email"):
        out["email"] = prof["email"]
    if prof.get("phone"):
        out["phone"] = prof["phone"]
    if prof.get("title"):
        out["title"] = prof["title"]
    if prof.get("displayName"):
        out["displayName"] = prof["displayName"]
    label = (
        prof.get("displayName")
        or prof.get("email")
        or prof.get("phone")
        or sub
    )
    out["displayLabel"] = label
    return out


# bootstrap profiles for seed subjects
seed_dev_persons()

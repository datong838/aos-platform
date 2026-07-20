"""200m — IdP subject ↔ verified email/phone linking MVP."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from aos_api import person_identity as person

_LINKS: list[dict[str, Any]] = []


def reset_account_links() -> None:
    _LINKS.clear()


def list_links_for_subject(subject: str) -> list[dict[str, Any]]:
    sub = (subject or "").strip()
    return [dict(x) for x in _LINKS if x.get("subject") == sub]


def find_subject_by_contact(
    *, email: str | None = None, phone: str | None = None
) -> str | None:
    if email:
        em = person.normalize_email(email)
        for row in _LINKS:
            if row.get("email") == em:
                return str(row["subject"])
    if phone:
        ph = person.normalize_phone(phone)
        for row in _LINKS:
            if row.get("phone") == ph:
                return str(row["subject"])
    return None


def create_link(
    *,
    subject: str,
    email: str | None = None,
    phone: str | None = None,
) -> dict[str, Any]:
    sub = (subject or "").strip()
    if not sub:
        raise ValueError("subject required")
    em = person.normalize_email(email) if email else None
    ph = person.normalize_phone(phone) if phone else None
    if not em and not ph:
        raise ValueError("email or phone required")
    # one contact → one subject
    for row in list(_LINKS):
        if em and row.get("email") == em and row.get("subject") != sub:
            raise ValueError("email already linked to another subject")
        if ph and row.get("phone") == ph and row.get("subject") != sub:
            raise ValueError("phone already linked to another subject")
        if row.get("subject") == sub and (
            (em and row.get("email") == em) or (ph and row.get("phone") == ph)
        ):
            return dict(row)
    row = {
        "id": f"lnk-{uuid.uuid4().hex[:10]}",
        "subject": sub,
        "email": em,
        "phone": ph,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    _LINKS.append(row)
    return dict(row)


def delete_link(*, subject: str, link_id: str) -> bool:
    sub = (subject or "").strip()
    lid = (link_id or "").strip()
    for i, row in enumerate(_LINKS):
        if row.get("id") == lid and row.get("subject") == sub:
            _LINKS.pop(i)
            return True
    return False

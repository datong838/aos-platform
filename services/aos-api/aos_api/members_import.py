"""194m — parse workspace members CSV (contacts import)."""
from __future__ import annotations

import csv
import io
import os
from typing import Any


def import_max_rows() -> int:
    raw = (os.environ.get("AOS_MEMBERS_IMPORT_MAX") or "200").strip()
    try:
        n = int(raw)
    except ValueError:
        return 200
    return max(1, min(n, 5000))


def _looks_like_header(cells: list[str]) -> bool:
    keys = {
        "email",
        "phone",
        "mobile",
        "tel",
        "displayname",
        "display_name",
        "name",
        "display",
        "role",
    }
    return any(c.strip().lower() in keys for c in cells)


def parse_members_csv(
    csv_text: str,
    *,
    default_role: str = "viewer",
    allowed_roles: set[str] | frozenset[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Parse CSV into member rows + per-line errors.
    Columns (header optional): email, phone, displayName, role
    At least one of email/phone required per data row.
    """
    roles = set(allowed_roles or {"owner", "admin", "editor", "viewer"})
    text = (csv_text or "").strip()
    if not text:
        return [], [{"line": 0, "message": "csv is empty"}]

    rows_raw = list(csv.reader(io.StringIO(text)))
    if not rows_raw:
        return [], [{"line": 0, "message": "csv is empty"}]

    start = 0
    colmap: dict[str, int] = {}
    if _looks_like_header(rows_raw[0]):
        for i, c in enumerate(rows_raw[0]):
            key = (c or "").strip().lower()
            if key == "email":
                colmap["email"] = i
            elif key in ("phone", "mobile", "tel"):
                colmap["phone"] = i
            elif key in ("displayname", "display_name", "name", "display"):
                colmap["displayName"] = i
            elif key == "role":
                colmap["role"] = i
        start = 1
    else:
        colmap = {"email": 0, "phone": 1, "displayName": 2, "role": 3}

    max_rows = import_max_rows()
    data_count = sum(1 for r in rows_raw[start:] if any((c or "").strip() for c in r))
    if data_count > max_rows:
        return [], [
            {
                "line": 0,
                "message": f"too many rows: {data_count} > max {max_rows}",
            }
        ]

    out: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    def cell(row: list[str], key: str) -> str:
        idx = colmap.get(key)
        if idx is None or idx >= len(row):
            return ""
        return (row[idx] or "").strip()

    for i, row in enumerate(rows_raw[start:], start=start + 1):
        if not any((c or "").strip() for c in row):
            continue
        email = cell(row, "email")
        phone = cell(row, "phone")
        display = cell(row, "displayName")
        role = cell(row, "role") or default_role

        # Single-column identity row (no header)
        if start == 0 and len([c for c in row if (c or "").strip()]) == 1:
            raw0 = (row[0] or "").strip()
            email, phone = ("", "")
            if "@" in raw0:
                email = raw0
            else:
                phone = raw0
            display = ""
            role = default_role
        elif start == 0 and not email and not phone and row:
            # positional: col0 may be email or phone
            raw0 = (row[0] or "").strip()
            if "@" in raw0:
                email = raw0
                phone = cell(row, "phone")
            else:
                phone = raw0
                email = ""

        if not email and not phone:
            errors.append({"line": i, "message": "email or phone required"})
            continue
        if role not in roles:
            errors.append({"line": i, "message": f"invalid role: {role}"})
            continue
        out.append(
            {
                "email": email or None,
                "phone": phone or None,
                "displayName": display or None,
                "role": role,
                "line": i,
            }
        )
    return out, errors

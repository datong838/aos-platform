"""Constitution Lint subset — T2.9 / 25 / T06 HR-02 style."""
from __future__ import annotations

from typing import Any

from aos_api.logging_facade import get_logger

log = get_logger("aos-api.constitution")

# Minimal OKF-inspired rules (Wave-2 subset)
RULES = [
    {
        "id": "C-PROP-01",
        "message": "published ObjectType must declare ≥1 property",
        "check": "published_requires_properties",
    },
    {
        "id": "C-ID-01",
        "message": "ObjectType id must be PascalCase / alphanumeric",
        "check": "id_pattern",
    },
]


def lint_object_type(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    oid = str(payload.get("id") or "")
    published = bool(payload.get("published") or payload.get("publish"))
    props = payload.get("properties") or []

    if published and len(props) < 1:
        errors.append({"rule": "C-PROP-01", "message": RULES[0]["message"]})
    if not oid or not oid[:1].isupper() or not oid.replace("_", "").isalnum():
        errors.append({"rule": "C-ID-01", "message": RULES[1]["message"]})

    ok = len(errors) == 0
    log.info("constitution_lint id=%s ok=%s errors=%s", oid, ok, len(errors))
    return {"ok": ok, "errors": errors, "rulesVersion": "wave2-subset-1"}

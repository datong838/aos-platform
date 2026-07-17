"""Submission Criteria engine — T3.2."""
from __future__ import annotations

from typing import Any

from aos_api.logging_facade import get_logger

log = get_logger("aos-api.submission")


def evaluate_criteria(
    criteria: list[dict[str, Any]] | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Minimal criteria DSL:
      {"field": "reason", "op": "required"}
      {"field": "priority", "op": "eq", "value": "P0"}
      {"field": "score", "op": "gte", "value": 1}
    Empty criteria ⇒ pass.
    """
    errors: list[dict[str, str]] = []
    criteria = criteria or []
    for rule in criteria:
        field = str(rule.get("field") or "")
        op = str(rule.get("op") or "required")
        expected = rule.get("value")
        actual = payload.get(field)
        if op == "required":
            if actual is None or actual == "":
                errors.append({"field": field, "rule": "required", "message": f"{field} is required"})
        elif op == "eq":
            if str(actual) != str(expected):
                errors.append(
                    {
                        "field": field,
                        "rule": "eq",
                        "message": f"{field} must equal {expected}",
                    }
                )
        elif op == "gte":
            try:
                if float(actual) < float(expected):
                    errors.append(
                        {
                            "field": field,
                            "rule": "gte",
                            "message": f"{field} must be >= {expected}",
                        }
                    )
            except (TypeError, ValueError):
                errors.append(
                    {
                        "field": field,
                        "rule": "gte",
                        "message": f"{field} not numeric",
                    }
                )
        else:
            errors.append({"field": field, "rule": op, "message": f"unknown op {op}"})
    ok = len(errors) == 0
    log.info("submission_criteria ok=%s errors=%s", ok, len(errors))
    return {"ok": ok, "errors": errors}

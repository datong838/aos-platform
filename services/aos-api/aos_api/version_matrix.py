"""TWB.7 — Hub ↔ desktop / spoke / ferry bundle version matrix."""
from __future__ import annotations

import re
from typing import Any, Literal

from aos_api.logging_facade import get_logger

log = get_logger("aos-api.version-matrix")

Status = Literal["ok", "warn", "block"]

# Hub control-plane declared compatibility (ops may override in-memory)
_MATRIX: dict[str, Any] = {
    "hubVersion": "0.3.0",
    "hubApi": "aos-api",
    "notes": "气隙端仅连控制面；Ferry 包与端/Spoke 版本须满足矩阵",
    "rules": [
        {
            "component": "desktop",
            "label": "AOS 桌面",
            "min": "0.2.0",
            "recommended": "0.2.0",
        },
        {
            "component": "spoke",
            "label": "Lite Spoke",
            "min": "0.3.0",
            "recommended": "0.3.0",
        },
        {
            "component": "ferryBundle",
            "label": "Ferry 包格式",
            "min": "1.0",
            "recommended": "1.1",
        },
    ],
}


def reset_version_matrix() -> None:
    global _MATRIX
    _MATRIX = {
        "hubVersion": "0.3.0",
        "hubApi": "aos-api",
        "notes": "气隙端仅连控制面；Ferry 包与端/Spoke 版本须满足矩阵",
        "rules": [
            {
                "component": "desktop",
                "label": "AOS 桌面",
                "min": "0.2.0",
                "recommended": "0.2.0",
            },
            {
                "component": "spoke",
                "label": "Lite Spoke",
                "min": "0.3.0",
                "recommended": "0.3.0",
            },
            {
                "component": "ferryBundle",
                "label": "Ferry 包格式",
                "min": "1.0",
                "recommended": "1.1",
            },
        ],
    }


def get_matrix() -> dict[str, Any]:
    return {
        "hubVersion": _MATRIX["hubVersion"],
        "hubApi": _MATRIX["hubApi"],
        "notes": _MATRIX["notes"],
        "rules": [dict(r) for r in _MATRIX["rules"]],
    }


def _digits(ver: str) -> tuple[int, int, int]:
    raw = (ver or "").strip()
    # strip pre-release / build
    raw = re.split(r"[-+]", raw, maxsplit=1)[0]
    parts = re.findall(r"\d+", raw)
    nums = [int(p) for p in parts[:3]]
    while len(nums) < 3:
        nums.append(0)
    return nums[0], nums[1], nums[2]


def version_gte(actual: str, minimum: str) -> bool:
    return _digits(actual) >= _digits(minimum)


def version_lt(actual: str, other: str) -> bool:
    return _digits(actual) < _digits(other)


def check_component(
    *,
    component: str,
    actual: str | None,
    rule: dict[str, Any],
) -> dict[str, Any]:
    if not actual or not str(actual).strip():
        return {
            "component": component,
            "label": rule.get("label") or component,
            "actual": None,
            "min": rule.get("min"),
            "recommended": rule.get("recommended"),
            "status": "warn",
            "reason": "version not reported",
        }
    actual_s = str(actual).strip()
    minimum = str(rule.get("min") or "0.0.0")
    recommended = str(rule.get("recommended") or minimum)
    if not version_gte(actual_s, minimum):
        return {
            "component": component,
            "label": rule.get("label") or component,
            "actual": actual_s,
            "min": minimum,
            "recommended": recommended,
            "status": "block",
            "reason": f"below minimum {minimum}",
        }
    if version_lt(actual_s, recommended):
        return {
            "component": component,
            "label": rule.get("label") or component,
            "actual": actual_s,
            "min": minimum,
            "recommended": recommended,
            "status": "warn",
            "reason": f"below recommended {recommended}",
        }
    return {
        "component": component,
        "label": rule.get("label") or component,
        "actual": actual_s,
        "min": minimum,
        "recommended": recommended,
        "status": "ok",
        "reason": "compatible",
    }


def check_versions(
    *,
    desktop: str | None = None,
    spoke: str | None = None,
    ferry_bundle: str | None = None,
) -> dict[str, Any]:
    reported = {
        "desktop": desktop,
        "spoke": spoke,
        "ferryBundle": ferry_bundle,
    }
    items: list[dict[str, Any]] = []
    for rule in _MATRIX["rules"]:
        comp = str(rule["component"])
        items.append(
            check_component(
                component=comp,
                actual=reported.get(comp),
                rule=rule,
            )
        )
    blocked = any(i["status"] == "block" for i in items)
    warned = any(i["status"] == "warn" for i in items)
    overall: Status = "block" if blocked else ("warn" if warned else "ok")
    log.info(
        "version_matrix_check overall=%s desktop=%s spoke=%s ferry=%s",
        overall,
        desktop,
        spoke,
        ferry_bundle,
    )
    return {
        "ok": overall == "ok",
        "overall": overall,
        "hubVersion": _MATRIX["hubVersion"],
        "items": items,
    }

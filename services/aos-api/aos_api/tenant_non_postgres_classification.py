"""TI-5 C3-C non-PostgreSQL mutable finding classification contract."""
from __future__ import annotations

from importlib import resources
from typing import Any

import yaml

SCHEMA_VERSION = "aos.dev/tenant-non-postgres-classification/v1alpha1"
CLASSIFICATIONS = frozenset(
    {
        "TENANT_OWNED_FIXED",
        "PLATFORM_TEMPLATE",
        "CONSTANT",
        "NOT_REACHABLE",
        "EXTERNAL_UNVERIFIED",
    }
)
NON_POSTGRES_RESOURCES = frozenset(
    {
        "tenant-object-prefixes",
        "tenant-vector-records",
        "tenant-cache-namespaces",
        "tenant-offline-storage",
        "tenant-message-queues",
        "tenant-scheduler-jobs",
        "tenant-process-memory",
    }
)


def load_classification() -> dict[str, Any]:
    raw = (
        resources.files("aos_api")
        .joinpath("tenant_non_postgres_classification.yaml")
        .read_text(encoding="utf-8")
    )
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise TypeError("classification root must be an object")
    return data


def validate_classification(data: dict[str, Any] | None = None) -> list[str]:
    document = data or load_classification()
    issues: list[str] = []
    if document.get("schemaVersion") != SCHEMA_VERSION:
        issues.append(f"schemaVersion must be {SCHEMA_VERSION}")
    entries = document.get("classifications")
    if not isinstance(entries, list) or not entries:
        return [*issues, "classifications must be a non-empty list"]

    ids: set[str] = set()
    covered_resources: set[str] = set()
    for index, entry in enumerate(entries):
        label = f"classifications[{index}]"
        if not isinstance(entry, dict):
            issues.append(f"{label} must be an object")
            continue
        item_id = str(entry.get("id") or "").strip()
        if not item_id:
            issues.append(f"{label}.id is required")
        elif item_id in ids:
            issues.append(f"{label}.id is duplicated: {item_id}")
        ids.add(item_id)
        classification = str(entry.get("classification") or "").strip()
        if classification not in CLASSIFICATIONS:
            issues.append(f"{label}.classification is invalid: {classification!r}")
        if not str(entry.get("runtimeStatus") or "").strip():
            issues.append(f"{label}.runtimeStatus is required")
        evidence = entry.get("evidence")
        if not isinstance(evidence, list) or not evidence or not all(
            isinstance(item, str) and item.strip() for item in evidence
        ):
            issues.append(f"{label}.evidence must be a non-empty string list")
        resource = str(entry.get("resource") or "").strip()
        if resource:
            covered_resources.add(resource)

    missing = sorted(NON_POSTGRES_RESOURCES - covered_resources)
    extra = sorted(covered_resources - NON_POSTGRES_RESOURCES)
    if missing:
        issues.append(f"missing non-PostgreSQL resources: {missing}")
    if extra:
        issues.append(f"unknown non-PostgreSQL resources: {extra}")
    return issues

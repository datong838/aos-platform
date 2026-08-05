from __future__ import annotations

from aos_api.tenant_non_postgres_classification import (
    NON_POSTGRES_RESOURCES,
    load_classification,
    validate_classification,
)
from aos_api.tenant_precheck import build_non_postgres_inventory


def test_c3c_classification_is_complete_and_valid() -> None:
    document = load_classification()
    assert validate_classification(document) == []
    resources = {
        item["resource"]
        for item in document["classifications"]
        if item.get("resource")
    }
    assert resources == NON_POSTGRES_RESOURCES


def test_unconfigured_external_backends_are_reported_without_probe_claims(
    monkeypatch,
) -> None:
    for name in (
        "AOS_REDIS_URL",
        "REDIS_URL",
        "AOS_BROKER_URL",
        "KAFKA_BOOTSTRAP_SERVERS",
        "RABBITMQ_URL",
    ):
        monkeypatch.delenv(name, raising=False)
    inventory = build_non_postgres_inventory(
        object_store_report={"status": "PROBED", "itemCount": 0},
        vector_report={"status": "PROBED", "itemCount": 0},
        process_memory_report={"status": "STATIC_ONLY", "findingCount": 0},
        scheduler_report={"status": "PROBED", "itemCount": 0},
    )
    by_name = {item["name"]: item for item in inventory["resources"]}
    assert by_name["tenant-cache-namespaces"]["status"] == "NOT_CONFIGURED"
    assert by_name["tenant-offline-storage"]["status"] == "NOT_CONFIGURED"
    assert by_name["tenant-message-queues"]["status"] == "NOT_CONFIGURED"

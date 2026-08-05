from __future__ import annotations

from importlib import resources

from aos_api.tenant_non_postgres_classification import (
    NON_POSTGRES_RESOURCES,
    load_classification,
    validate_classification,
)
from aos_api.tenant_precheck import build_non_postgres_inventory


def test_c3c_classification_is_complete_and_valid() -> None:
    document = load_classification()
    assert validate_classification(document) == []
    resources_set = {
        item["resource"]
        for item in document["classifications"]
        if item.get("resource")
    }
    assert resources_set == NON_POSTGRES_RESOURCES


def test_c3c_evidence_paths_point_to_real_files() -> None:
    document = load_classification()
    issues = validate_classification(document)
    evidence_issues = [issue for issue in issues if "evidence" in issue.lower()]
    assert evidence_issues == [], evidence_issues


def test_c3c_every_evidence_path_resolves_under_package() -> None:
    package_root = resources.files("aos_api")
    document = load_classification()
    missing = []
    for entry in document["classifications"]:
        for evidence in entry.get("evidence", []):
            relative = evidence.split(":", 1)[0]
            if relative.startswith("aos_api/"):
                relative = relative[len("aos_api/") :]
            if not package_root.joinpath(relative).is_file():
                missing.append(f"{entry['id']} -> {evidence}")
    assert missing == [], f"evidence paths do not exist: {missing}"


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

from __future__ import annotations

import importlib.util
from contextlib import contextmanager
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[4] / "scripts/aip/inspect_r21_content_text_chain.py"
SPEC = importlib.util.spec_from_file_location("inspect_r21_content_text_chain", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class Result:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, scope, *, bad_hash: bool = False, dirty_canary: bool = False):
        self.scope = scope
        self.bad_hash = bad_hash
        self.dirty_canary = dirty_canary
        self.sql: list[str] = []

    def execute(self, sql, _params):
        normalized = " ".join(sql.split())
        self.sql.append(normalized)
        if "aip_agent_run_execution_attempt" in normalized:
            return Result(
                [
                    {
                        "attempt_id": module.ATTEMPT_ID,
                        "agent_run_id": "ecommerce.content_officer.C02.real-pilot.v1",
                        "status": "succeeded",
                        "output_artifact_ref": {
                            "artifactId": "artifact-c02",
                            "contentHash": "0" * 64 if self.bad_hash else module.EXPECTED_OUTPUT_HASH,
                        },
                        "lineage_id": "lineage-c02",
                        "provider_receipt_id": "provider-receipt-c02",
                        "usage_receipt_ids": ["usage-1", "usage-2"],
                        "completed_at": "2026-08-18T17:37:06Z",
                    }
                ]
            )
        if "FROM aip_artifact" in normalized:
            return Result(
                [
                    {
                        "artifact_id": "artifact-c02",
                        "run_id": "run-c02",
                        "artifact_type": "agent_text_output",
                        "content_hash": module.EXPECTED_OUTPUT_HASH,
                        "created_at": "2026-08-18T17:37:06Z",
                    }
                ]
            )
        if "FROM aip_usage_receipt" in normalized:
            return Result([{"count": 2}])
        if "FROM aip_lineage_event" in normalized:
            return Result([{"count": 3}])
        if "FROM ecom_object" in normalized and "LIMIT 3" in normalized:
            return Result(
                [
                    {
                        "external_id": "niushop:1:59",
                        "title": "399白钻逆龄双效王炸套装",
                        "status": "active",
                        "price": "399.00",
                        "stock": "497.000",
                        "payload_hash": "a" * 64,
                        "source_updated_at": "2026-06-22T09:44:00Z",
                    }
                ]
            )
        if "FROM ecom_object" in normalized:
            return Result([{"count": 1 if self.dirty_canary else 0}])
        raise AssertionError(normalized)


def factory(*, bad_hash: bool = False, dirty_canary: bool = False):
    connections = []

    @contextmanager
    def open_connection(scope):
        conn = Connection(scope, bad_hash=bad_hash, dirty_canary=dirty_canary)
        connections.append(conn)
        yield conn

    return open_connection, connections


def test_inspector_returns_metadata_only_and_does_not_overclaim_product_binding():
    open_connection, connections = factory()

    result = module.inspect(connection_factory=open_connection)

    assert result["status"] == "HISTORICAL_PROVIDER_TRACE_GREEN_REAL_PRODUCT_LINK_NOT_PROVEN"
    assert result["attempt"]["lineageEventCount"] == 3
    assert result["realProducts"][0]["title"] == "399白钻逆龄双效王炸套装"
    assert result["sameProductBoundToHistoricalPilot"] is False
    assert result["providerCalls"] == 0
    assert result["databaseWrites"] == 0
    assert result["artifactBodiesRead"] == 0
    assert result["secretPayloadReads"] == 0
    statements = " ".join(sql for conn in connections for sql in conn.sql).lower()
    assert "content_ref" not in statements
    assert " insert " not in f" {statements} "
    assert " update " not in f" {statements} "
    assert " delete " not in f" {statements} "


def test_inspector_fails_closed_on_hash_drift_and_dirty_canary():
    bad_hash, _ = factory(bad_hash=True)
    with pytest.raises(module.InspectionBlocked, match="C02_OUTPUT_HASH_DRIFTED"):
        module.inspect(connection_factory=bad_hash)

    dirty_canary, _ = factory(dirty_canary=True)
    with pytest.raises(module.InspectionBlocked, match="NEGATIVE_CANARY_DIRTY"):
        module.inspect(connection_factory=dirty_canary)

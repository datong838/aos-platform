#!/usr/bin/env python3
"""Read-only R21 Product and immutable C02 execution metadata inspection.

The inspector intentionally excludes artifact bodies, prompts, answers, secret
payloads, headers and cookies.  It proves that a real Product projection and a
real historical Provider execution both exist; it does not claim that the C02
pilot was bound to that Product because the immutable pilot had no Product ref.
"""
from __future__ import annotations

import argparse
import json
from contextlib import AbstractContextManager
from typing import Any, Callable

from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

REAL_SCOPE = TenantScope("org-org", "dev-project")
CANARY_SCOPE = TenantScope("dev-org", "dev-project")
ATTEMPT_ID = "ecommerce.content_officer.C02.real-pilot.v1.attempt-1"
EXPECTED_OUTPUT_HASH = (
    "f5b368f86cb04d3782b4971bc131606fa5e3d492302eaae7eba48742a14cb209"
)

ConnectionFactory = Callable[[TenantScope], AbstractContextManager[Any]]


class InspectionBlocked(RuntimeError):
    pass


def _one(conn: Any, sql: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row is not None else None


def inspect(*, connection_factory: ConnectionFactory = connect) -> dict[str, Any]:
    with connection_factory(REAL_SCOPE) as conn:
        attempt = _one(
            conn,
            """SELECT attempt_id,agent_run_id,status,output_artifact_ref,lineage_id,
                      provider_receipt_id,usage_receipt_ids,completed_at
                 FROM aip_agent_run_execution_attempt
                WHERE org_id=%s AND project_id=%s AND attempt_id=%s""",
            (*REAL_SCOPE.key, ATTEMPT_ID),
        )
        if attempt is None or attempt["status"] != "succeeded":
            raise InspectionBlocked("C02_IMMUTABLE_ATTEMPT_NOT_SUCCEEDED")
        artifact_ref = dict(attempt["output_artifact_ref"] or {})
        if artifact_ref.get("contentHash") != EXPECTED_OUTPUT_HASH:
            raise InspectionBlocked("C02_OUTPUT_HASH_DRIFTED")
        artifact = _one(
            conn,
            """SELECT artifact_id,run_id,artifact_type,content_hash,created_at
                 FROM aip_artifact
                WHERE org_id=%s AND project_id=%s AND artifact_id=%s""",
            (*REAL_SCOPE.key, artifact_ref.get("artifactId")),
        )
        usage_count = _one(
            conn,
            """SELECT COUNT(*) AS count FROM aip_usage_receipt
                WHERE org_id=%s AND project_id=%s AND receipt_id=ANY(%s)""",
            (*REAL_SCOPE.key, attempt["usage_receipt_ids"]),
        )
        lineage_count = _one(
            conn,
            """SELECT COUNT(*) AS count FROM aip_lineage_event
                WHERE org_id=%s AND project_id=%s AND lineage_id=%s""",
            (*REAL_SCOPE.key, attempt["lineage_id"]),
        )
        products = conn.execute(
            """SELECT external_id,properties->>'title' AS title,
                      properties->>'status' AS status,properties->>'price' AS price,
                      properties->>'stock' AS stock,payload_hash,source_updated_at
                 FROM ecom_object
                WHERE org_id=%s AND workspace_id=%s AND object_type='Product'
                  AND properties->>'status'='active'
                ORDER BY source_updated_at DESC NULLS LAST,external_id
                LIMIT 3""",
            REAL_SCOPE.key,
        ).fetchall()
    with connection_factory(CANARY_SCOPE) as conn:
        canary = _one(
            conn,
            """SELECT COUNT(*) AS count FROM ecom_object
                WHERE org_id=%s AND workspace_id=%s AND object_type='Product'""",
            CANARY_SCOPE.key,
        )

    if artifact is None or artifact["content_hash"] != EXPECTED_OUTPUT_HASH:
        raise InspectionBlocked("C02_ARTIFACT_METADATA_INCOMPLETE")
    expected_usage = len(attempt["usage_receipt_ids"] or [])
    if int((usage_count or {}).get("count", 0)) != expected_usage:
        raise InspectionBlocked("C02_USAGE_RECEIPT_CHAIN_INCOMPLETE")
    if int((lineage_count or {}).get("count", 0)) < 1:
        raise InspectionBlocked("C02_LINEAGE_CHAIN_INCOMPLETE")
    if not products:
        raise InspectionBlocked("REAL_ACTIVE_PRODUCT_MISSING")
    if int((canary or {}).get("count", 0)) != 0:
        raise InspectionBlocked("NEGATIVE_CANARY_DIRTY")

    return {
        "status": "HISTORICAL_PROVIDER_TRACE_GREEN_REAL_PRODUCT_LINK_NOT_PROVEN",
        "tenant": {"orgId": REAL_SCOPE.org_id, "projectId": REAL_SCOPE.project_id},
        "attempt": {
            "attemptId": attempt["attempt_id"],
            "agentRunId": attempt["agent_run_id"],
            "status": attempt["status"],
            "completedAt": attempt["completed_at"],
            "providerReceiptPresent": bool(attempt["provider_receipt_id"]),
            "usageReceiptCount": expected_usage,
            "artifactId": artifact["artifact_id"],
            "artifactType": artifact["artifact_type"],
            "outputContentHash": artifact["content_hash"],
            "lineageId": attempt["lineage_id"],
            "lineageEventCount": int(lineage_count["count"]),
        },
        "realProducts": [
            {
                "productRef": f"Product:{row['external_id']}@{row['payload_hash']}#{row['payload_hash']}",
                "title": row["title"],
                "status": row["status"],
                "price": row["price"],
                "stock": row["stock"],
                "sourceUpdatedAt": row["source_updated_at"],
            }
            for row in products
        ],
        "negativeCanaryProductCount": 0,
        "sameProductBoundToHistoricalPilot": False,
        "operationalStatus": "BLOCKED_NEW_UNIQUE_PRODUCT_PILOT_AND_FRESH_3_OF_3_HEALTH_REQUIRED",
        "providerCalls": 0,
        "databaseWrites": 0,
        "artifactBodiesRead": 0,
        "secretPayloadReads": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = inspect()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

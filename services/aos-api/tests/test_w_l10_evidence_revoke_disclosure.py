"""W-L10 EvidenceBundle revoke + Disclosure/Marking API."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from aos_api.aip_task_models import CreateTaskRequest
from aos_api.aip_task_store import AipTaskStore
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

ORG = TenantScope("org-org", "dev-project")
ACTOR = "user:dev"
EVIDENCE_ACTOR = "test:w-l10-api"


def headers(org="org-org", key=None):
    out = {
        "Authorization": "Bearer dev",
        "X-Org-Id": org,
        "X-Project-Id": "dev-project",
    }
    if key:
        out["Idempotency-Key"] = key
    return out


def cleanup():
    with connect(ORG) as c:
        c.execute(
            "DELETE FROM aip_evidence_disclosure_decision WHERE org_id=%s AND project_id=%s AND actor=%s",
            (*ORG.key, ACTOR),
        )
        c.execute(
            "DELETE FROM aip_evidence_bundle_revoke_event WHERE org_id=%s AND project_id=%s AND actor=%s",
            (*ORG.key, ACTOR),
        )
        bundle_ids = [
            r["bundle_id"]
            for r in c.execute(
                "SELECT bundle_id FROM aip_evidence_bundle_revision WHERE org_id=%s AND project_id=%s AND created_by=%s",
                (*ORG.key, ACTOR),
            ).fetchall()
        ]
        brief_ids = []
        ids = [
            r["task_id"]
            for r in c.execute(
                "SELECT task_id FROM aip_task WHERE org_id=%s AND project_id=%s AND title LIKE 'W-L10 %%'",
                ORG.key,
            ).fetchall()
        ]
        if ids:
            brief_ids = [
                r["brief_id"]
                for r in c.execute(
                    "SELECT brief_id FROM aip_task_brief_head WHERE org_id=%s AND project_id=%s AND task_id=ANY(%s)",
                    (*ORG.key, ids),
                ).fetchall()
            ]
        resource_ids = brief_ids + bundle_ids
        if resource_ids:
            c.execute(
                "DELETE FROM aip_production_contract_receipt WHERE org_id=%s AND project_id=%s AND result_ref->>'resourceId'=ANY(%s)",
                (*ORG.key, resource_ids),
            )
        c.execute(
            "DELETE FROM aip_evidence_bundle_revision WHERE org_id=%s AND project_id=%s AND created_by=%s",
            (*ORG.key, ACTOR),
        )
        if ids:
            c.execute(
                "DELETE FROM aip_task_brief_revision WHERE org_id=%s AND project_id=%s AND task_id=ANY(%s)",
                (*ORG.key, ids),
            )
        for task_id in ids:
            c.execute(
                "DELETE FROM aip_task_brief_head WHERE org_id=%s AND project_id=%s AND task_id=%s",
                (*ORG.key, task_id),
            )
        c.execute(
            "DELETE FROM aip_evidence WHERE org_id=%s AND project_id=%s AND created_by=%s AND source_ref='w-l10-api'",
            (*ORG.key, EVIDENCE_ACTOR),
        )
        for task_id in ids:
            c.execute(
                "DELETE FROM aip_task WHERE org_id=%s AND project_id=%s AND task_id=%s",
                (*ORG.key, task_id),
            )
        c.commit()


def _frozen_brief_and_evidence(client, *, marking: list[str], evidence_payload: dict):
    task = AipTaskStore().create_task(
        ORG, ACTOR, f"wl10-task-{uuid.uuid4().hex}", CreateTaskRequest(title="W-L10 revoke disclosure")
    )
    created = client.post(
        "/v1/aip/production-contracts/task-briefs",
        headers=headers(key=f"brief-{uuid.uuid4().hex}"),
        json={
            "taskId": task.id,
            "briefType": "ecommerce.analysis",
            "schemaRef": {
                "resourceType": "Schema",
                "resourceId": "analysis",
                "revision": "1",
                "authority": "aip",
            },
            "spec": {"goal": "w-l10"},
        },
    )
    assert created.status_code == 201, created.text
    draft = created.json()
    frozen_response = client.post(
        f"/v1/aip/production-contracts/task-briefs/{draft['briefId']}/freeze",
        headers=headers(key=f"freeze-{uuid.uuid4().hex}"),
        json={"expectedVersion": draft["version"]},
    )
    assert frozen_response.status_code == 200, frozen_response.text
    frozen = frozen_response.json()
    evidence_id = f"ev-l10-{uuid.uuid4().hex[:18]}"
    evidence_hash = "d" * 64
    with connect(ORG) as conn:
        conn.execute(
            """INSERT INTO aip_evidence(org_id,project_id,evidence_id,evidence_type,subject_ref,source_type,source_ref,observed_at,freshness_at,content_hash,payload,created_by)
            VALUES(%s,%s,%s,'order_fact','{}','database','w-l10-api',NOW(),NOW(),%s,%s::jsonb,%s)""",
            (
                *ORG.key,
                evidence_id,
                evidence_hash,
                __import__("json").dumps(evidence_payload),
                EVIDENCE_ACTOR,
            ),
        )
        conn.commit()
    payload = {
        "briefRef": {
            "resourceType": "TaskBriefRevision",
            "resourceId": frozen["briefId"],
            "revision": frozen["revision"],
            "contentHash": frozen["contentHash"],
        },
        "subjectRefs": [],
        "cutoffAt": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        "itemRefs": [
            {
                "resourceType": "Evidence",
                "resourceId": evidence_id,
                "revision": 1,
                "contentHash": evidence_hash,
            }
        ],
        "requiredFactIds": ["order_snapshot"],
        "marking": marking,
        "licenseSummary": {"source": "w-l10"},
    }
    response = client.post(
        "/v1/aip/production-contracts/evidence-bundles/build",
        headers=headers(key=f"bundle-{uuid.uuid4().hex}"),
        json=payload,
    )
    assert response.status_code == 201, response.text
    return frozen, evidence_id, evidence_hash, response.json()


def test_revoke_marks_bundle_and_blocks_disclosure(client):
    cleanup()
    try:
        _, evidence_id, evidence_hash, bundle = _frozen_brief_and_evidence(
            client,
            marking=["public"],
            evidence_payload={"factIds": ["order_snapshot"], "marking": ["public"]},
        )
        revoke = client.post(
            f"/v1/aip/production-contracts/evidence-bundles/{bundle['bundleId']}/revoke",
            headers=headers(key=f"revoke-{uuid.uuid4().hex}"),
            json={
                "expectedRevision": bundle["revision"],
                "expectedContentHash": bundle["contentHash"],
                "reason": "stale facts after cutoff",
            },
        )
        assert revoke.status_code == 200, revoke.text
        revoked = revoke.json()
        assert revoked["revoked"] is True
        assert revoked["revokeReason"] == "stale facts after cutoff"
        assert revoked["contentHash"] == bundle["contentHash"]
        got = client.get(
            f"/v1/aip/production-contracts/evidence-bundles/{bundle['bundleId']}",
            headers=headers(),
        )
        assert got.status_code == 200 and got.json()["revoked"] is True
        disc_key = f"disc-{uuid.uuid4().hex}"
        disclosure = client.post(
            "/v1/aip/evidence/disclosures/resolve",
            headers=headers(key=disc_key),
            json={
                "evidenceRef": {
                    "resourceType": "Evidence",
                    "resourceId": evidence_id,
                    "revision": 1,
                    "contentHash": evidence_hash,
                },
                "purpose": "preview",
                "requestedLevel": "l1",
            },
        )
        assert disclosure.status_code == 201, disclosure.text
        body = disclosure.json()
        assert body["status"] == "blocked"
        assert "EVIDENCE_BUNDLE_REVOKED" in body["reasons"]
        replay = client.post(
            "/v1/aip/evidence/disclosures/resolve",
            headers=headers(key=disc_key),
            json={
                "evidenceRef": {
                    "resourceType": "Evidence",
                    "resourceId": evidence_id,
                    "revision": 1,
                    "contentHash": evidence_hash,
                },
                "purpose": "preview",
                "requestedLevel": "l1",
            },
        )
        assert replay.status_code == 201
        assert replay.json()["decisionId"] == body["decisionId"]
        fetched = client.get(
            f"/v1/aip/evidence/disclosures/{body['decisionId']}",
            headers=headers(),
        )
        assert fetched.status_code == 200
        assert fetched.json()["decisionHash"] == body["decisionHash"]
    finally:
        cleanup()


def test_marking_gate_hides_secret_bundle_and_gates_l2_l3(client):
    cleanup()
    try:
        _, evidence_id, evidence_hash, bundle = _frozen_brief_and_evidence(
            client,
            marking=["secret"],
            evidence_payload={"factIds": ["order_snapshot"], "marking": ["public"]},
        )
        listing = client.get("/v1/aip/production-contracts/evidence-bundles", headers=headers())
        assert listing.status_code == 200
        assert all(item["bundleId"] != bundle["bundleId"] for item in listing.json()["items"])
        assert (
            client.get(
                f"/v1/aip/production-contracts/evidence-bundles/{bundle['bundleId']}",
                headers=headers(),
            ).status_code
            == 404
        )
        l1 = client.post(
            "/v1/aip/evidence/disclosures/resolve",
            headers=headers(key=f"l1-{uuid.uuid4().hex}"),
            json={
                "evidenceRef": {
                    "resourceType": "Evidence",
                    "resourceId": evidence_id,
                    "revision": 1,
                    "contentHash": evidence_hash,
                },
                "purpose": "summary",
                "requestedLevel": "l1",
            },
        )
        assert l1.status_code == 201 and l1.json()["status"] == "allowed"
        assert l1.json()["grantedLevel"] == "l1"
        l2 = client.post(
            "/v1/aip/evidence/disclosures/resolve",
            headers=headers(key=f"l2-{uuid.uuid4().hex}"),
            json={
                "evidenceRef": {
                    "resourceType": "Evidence",
                    "resourceId": evidence_id,
                    "revision": 1,
                    "contentHash": evidence_hash,
                },
                "purpose": "excerpt",
                "requestedLevel": "l2",
            },
        )
        assert l2.status_code == 201 and l2.json()["status"] == "allowed"
        l3 = client.post(
            "/v1/aip/evidence/disclosures/resolve",
            headers=headers(key=f"l3-{uuid.uuid4().hex}"),
            json={
                "evidenceRef": {
                    "resourceType": "Evidence",
                    "resourceId": evidence_id,
                    "revision": 1,
                    "contentHash": evidence_hash,
                },
                "purpose": "source",
                "requestedLevel": "l3",
            },
        )
        assert l3.status_code == 201
        assert l3.json()["status"] == "blocked"
        assert "L3_REQUIRES_SECRET_MARKING" in l3.json()["reasons"]
    finally:
        cleanup()

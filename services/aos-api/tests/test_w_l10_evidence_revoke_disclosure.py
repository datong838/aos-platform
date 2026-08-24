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
        # W4-01 makes base Evidence append-only. Every test uses a unique
        # evidence id, so retain the immutable source row during cleanup.
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


def test_source_evidence_revoke_is_exact_idempotent_and_blocks_new_bundle(client):
    cleanup()
    try:
        frozen, evidence_id, evidence_hash, _ = _frozen_brief_and_evidence(
            client,
            marking=["public"],
            evidence_payload={"factIds": ["order_snapshot"], "marking": ["public"]},
        )
        revoke_key = f"evidence-revoke-{uuid.uuid4().hex}"
        revoke_payload = {
            "expectedRevision": 1,
            "expectedContentHash": evidence_hash,
            "reason": "canonical source invalidated",
        }
        revoked = client.post(
            f"/v1/aip/production-contracts/evidence/{evidence_id}/revoke",
            headers=headers(key=revoke_key),
            json=revoke_payload,
        )
        assert revoked.status_code == 200, revoked.text
        body = revoked.json()
        assert body["evidenceRef"] == {
            "resourceType": "Evidence",
            "resourceId": evidence_id,
            "revision": 1,
            "contentHash": evidence_hash,
        }
        assert body["reason"] == "canonical source invalidated"
        replay = client.post(
            f"/v1/aip/production-contracts/evidence/{evidence_id}/revoke",
            headers=headers(key=revoke_key),
            json=revoke_payload,
        )
        assert replay.status_code == 200
        assert replay.json()["eventId"] == body["eventId"]
        assert (
            client.post(
                f"/v1/aip/production-contracts/evidence/{evidence_id}/revoke",
                headers=headers(org="dev-org", key=f"canary-{uuid.uuid4().hex}"),
                json=revoke_payload,
            ).status_code
            == 404
        )

        rebuilt = client.post(
            "/v1/aip/production-contracts/evidence-bundles/build",
            headers=headers(key=f"rebuilt-{uuid.uuid4().hex}"),
            json={
                "briefRef": {
                    "resourceType": "TaskBriefRevision",
                    "resourceId": frozen["briefId"],
                    "revision": frozen["revision"],
                    "contentHash": frozen["contentHash"],
                },
                "subjectRefs": [],
                "cutoffAt": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
                "itemRefs": [body["evidenceRef"]],
                "requiredFactIds": ["order_snapshot"],
                "marking": ["public"],
                "licenseSummary": {"source": "w4-01-source-revoke"},
            },
        )
        assert rebuilt.status_code == 422, rebuilt.text
        assert rebuilt.json()["code"] == "AIP_DEPENDENCY_BLOCKED"
        assert rebuilt.json()["message"] == "EVIDENCE_REVOKED"
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


def test_l2_citation_is_exact_and_license_purpose_is_rechecked(client):
    cleanup()
    try:
        _, evidence_id, evidence_hash, bundle = _frozen_brief_and_evidence(
            client,
            marking=["public"],
            evidence_payload={
                "factIds": ["order_snapshot"],
                "marking": ["public"],
                "excerpt": "订单事实最小引用片段",
                "sourceLocator": {"table": "orders", "row": "order-1"},
                "license": {"status": "allowed", "allowedPurposes": ["excerpt"]},
                "applicability": {"status": "applicable"},
                "freshUntil": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            },
        )
        response = client.post(
            "/v1/aip/evidence/disclosures/resolve",
            headers=headers(key=f"l2-exact-{uuid.uuid4().hex}"),
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
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["status"] == "allowed"
        assert body["displayPayload"]["excerpt"] == "订单事实最小引用片段"
        assert body["citation"]["evidenceRef"]["contentHash"] == evidence_hash
        assert body["citation"]["locator"] == {"table": "orders", "row": "order-1"}
        assert body["citation"]["excerptHash"] == body["displayPayload"]["excerptHash"]
        assert body["citation"]["auditRef"]["resourceId"] == body["decisionId"]
        assert body["redactionReceipt"]["bodyReturned"] is True
        assert client.get(
            f"/v1/aip/evidence/disclosures/{body['decisionId']}", headers=headers()
        ).status_code == 200

        with connect(ORG) as conn:
            conn.execute(
                """UPDATE aip_evidence_disclosure_decision SET expires_at=%s
                   WHERE org_id=%s AND project_id=%s AND decision_id=%s""",
                (
                    datetime.now(timezone.utc) - timedelta(seconds=1),
                    *ORG.key,
                    body["decisionId"],
                ),
            )
            conn.commit()
        expired_read = client.get(
            f"/v1/aip/evidence/disclosures/{body['decisionId']}", headers=headers()
        )
        assert expired_read.status_code == 422
        assert expired_read.json()["message"] == "EVIDENCE_DISCLOSURE_NO_LONGER_ALLOWED"
        with connect(ORG) as conn:
            conn.execute(
                """UPDATE aip_evidence_disclosure_decision SET expires_at=NULL
                   WHERE org_id=%s AND project_id=%s AND decision_id=%s""",
                (*ORG.key, body["decisionId"]),
            )
            conn.commit()

        denied = client.post(
            "/v1/aip/evidence/disclosures/resolve",
            headers=headers(key=f"purpose-denied-{uuid.uuid4().hex}"),
            json={
                "evidenceRef": {
                    "resourceType": "Evidence",
                    "resourceId": evidence_id,
                    "revision": 1,
                    "contentHash": evidence_hash,
                },
                "purpose": "summary",
                "requestedLevel": "l2",
            },
        )
        assert denied.status_code == 201
        assert denied.json()["status"] == "blocked"
        assert "PURPOSE_LEVEL_DENIED" in denied.json()["reasons"]
        assert "LICENSE_PURPOSE_DENIED" in denied.json()["reasons"]
        assert denied.json()["displayPayload"] == {}
        assert denied.json()["redactionReceipt"]["bodyReturned"] is False

        revoked = client.post(
            f"/v1/aip/production-contracts/evidence-bundles/{bundle['bundleId']}/revoke",
            headers=headers(key=f"revoke-after-disclosure-{uuid.uuid4().hex}"),
            json={
                "expectedRevision": bundle["revision"],
                "expectedContentHash": bundle["contentHash"],
                "reason": "license boundary changed",
            },
        )
        assert revoked.status_code == 200
        historical_read = client.get(
            f"/v1/aip/evidence/disclosures/{body['decisionId']}", headers=headers()
        )
        assert historical_read.status_code == 422
        assert historical_read.json()["message"] == "EVIDENCE_DISCLOSURE_NO_LONGER_ALLOWED"
    finally:
        cleanup()


def test_license_stale_tamper_and_cross_tenant_decision_fail_closed(client):
    cleanup()
    try:
        _, denied_id, denied_hash, _ = _frozen_brief_and_evidence(
            client,
            marking=["public"],
            evidence_payload={
                "factIds": ["order_snapshot"],
                "marking": ["public"],
                "license": {"status": "denied", "allowedPurposes": []},
            },
        )
        denied = client.post(
            "/v1/aip/evidence/disclosures/resolve",
            headers=headers(key=f"license-denied-{uuid.uuid4().hex}"),
            json={
                "evidenceRef": {
                    "resourceType": "Evidence",
                    "resourceId": denied_id,
                    "revision": 1,
                    "contentHash": denied_hash,
                },
                "purpose": "summary",
                "requestedLevel": "l1",
            },
        )
        assert denied.status_code == 201
        assert denied.json()["status"] == "blocked"
        assert "LICENSE_DENIED" in denied.json()["reasons"]
        assert denied.json()["displayPayload"] == {}

        _, stale_id, stale_hash, _ = _frozen_brief_and_evidence(
            client,
            marking=["public"],
            evidence_payload={
                "factIds": ["order_snapshot"],
                "marking": ["public"],
                "license": {"status": "allowed", "allowedPurposes": ["summary"]},
                "freshUntil": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
            },
        )
        stale = client.post(
            "/v1/aip/evidence/disclosures/resolve",
            headers=headers(key=f"stale-{uuid.uuid4().hex}"),
            json={
                "evidenceRef": {
                    "resourceType": "Evidence",
                    "resourceId": stale_id,
                    "revision": 1,
                    "contentHash": stale_hash,
                },
                "purpose": "summary",
                "requestedLevel": "l1",
            },
        )
        assert stale.status_code == 201
        assert stale.json()["status"] == "stale"
        assert stale.json()["displayPayload"] == {}

        tampered = client.post(
            "/v1/aip/evidence/disclosures/resolve",
            headers=headers(key=f"tampered-{uuid.uuid4().hex}"),
            json={
                "evidenceRef": {
                    "resourceType": "Evidence",
                    "resourceId": stale_id,
                    "revision": 1,
                    "contentHash": "f" * 64,
                },
                "purpose": "summary",
                "requestedLevel": "l1",
            },
        )
        assert tampered.status_code == 201
        assert tampered.json()["status"] == "blocked"
        assert "EVIDENCE_EXACT_REF_MISSING_OR_DRIFTED" in tampered.json()["reasons"]
        assert tampered.json()["displayPayload"] == {}
        decision_id = tampered.json()["decisionId"]

        wrong_revision = client.post(
            "/v1/aip/evidence/disclosures/resolve",
            headers=headers(key=f"wrong-revision-{uuid.uuid4().hex}"),
            json={
                "evidenceRef": {
                    "resourceType": "Evidence",
                    "resourceId": stale_id,
                    "revision": 2,
                    "contentHash": stale_hash,
                },
                "purpose": "summary",
                "requestedLevel": "l1",
            },
        )
        assert wrong_revision.status_code == 201
        assert wrong_revision.json()["status"] == "blocked"
        assert "EVIDENCE_EXACT_REF_MISSING_OR_DRIFTED" in wrong_revision.json()["reasons"]
        assert wrong_revision.json()["displayPayload"] == {}

        wrong_type = client.post(
            "/v1/aip/evidence/disclosures/resolve",
            headers=headers(key=f"wrong-type-{uuid.uuid4().hex}"),
            json={
                "evidenceRef": {
                    "resourceType": "EvidenceBundleRevision",
                    "resourceId": stale_id,
                    "revision": 1,
                    "contentHash": stale_hash,
                },
                "purpose": "summary",
                "requestedLevel": "l1",
            },
        )
        assert wrong_type.status_code == 400

        assert client.get(
            f"/v1/aip/evidence/disclosures/{decision_id}",
            headers=headers(org="dev-org"),
        ).status_code == 404

        invalid_purpose = client.post(
            "/v1/aip/evidence/disclosures/resolve",
            headers=headers(key=f"invalid-purpose-{uuid.uuid4().hex}"),
            json={
                "evidenceRef": {
                    "resourceType": "Evidence",
                    "resourceId": stale_id,
                    "revision": 1,
                    "contentHash": stale_hash,
                },
                "purpose": "free-form-client-purpose",
                "requestedLevel": "l1",
            },
        )
        assert invalid_purpose.status_code == 400
    finally:
        cleanup()

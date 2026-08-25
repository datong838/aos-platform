from __future__ import annotations
import uuid
from datetime import datetime, timedelta, timezone

from aos_api.aip_task_models import CreateTaskRequest
from aos_api.aip_task_store import AipTaskStore
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

ORG=TenantScope("org-org","dev-project")
ACTOR="user:dev"
EVIDENCE_ACTOR="test:w2a-api"


def headers(org="org-org",key=None):
    out={"Authorization":"Bearer dev","X-Org-Id":org,"X-Project-Id":"dev-project"}
    if key:out["Idempotency-Key"]=key
    return out


def cleanup():
    with connect(ORG) as c:
        ids=[r["task_id"] for r in c.execute("SELECT task_id FROM aip_task WHERE org_id=%s AND project_id=%s AND title LIKE 'W2A API %%'",ORG.key).fetchall()]
        brief_ids=[]
        if ids:
            brief_ids=[r["brief_id"] for r in c.execute(
                "SELECT brief_id FROM aip_task_brief_head WHERE org_id=%s AND project_id=%s AND task_id=ANY(%s)",
                (*ORG.key,ids),
            ).fetchall()]
        bundle_ids=[r["bundle_id"] for r in c.execute(
            "SELECT bundle_id FROM aip_evidence_bundle_revision WHERE org_id=%s AND project_id=%s AND created_by=%s",
            (*ORG.key,ACTOR),
        ).fetchall()]
        resource_ids=brief_ids+bundle_ids
        if resource_ids:
            c.execute(
                "DELETE FROM aip_production_contract_receipt WHERE org_id=%s AND project_id=%s AND result_ref->>'resourceId'=ANY(%s)",
                (*ORG.key,resource_ids),
            )
        c.execute(
            "DELETE FROM aip_evidence_bundle_revision WHERE org_id=%s AND project_id=%s AND created_by=%s",
            (*ORG.key,ACTOR),
        )
        if ids:
            c.execute("DELETE FROM aip_task_brief_revision WHERE org_id=%s AND project_id=%s AND task_id=ANY(%s)",(*ORG.key,ids))
        for task_id in ids:
            c.execute("DELETE FROM aip_task_brief_head WHERE org_id=%s AND project_id=%s AND task_id=%s",(*ORG.key,task_id))
        # Base Evidence is append-only from W4-01 onward. Every API test row has
        # a unique evidence_id, so preserving it is both isolated and faithful
        # to the production immutability contract.
        for task_id in ids:
            c.execute("DELETE FROM aip_task WHERE org_id=%s AND project_id=%s AND task_id=%s",(*ORG.key,task_id))
        c.commit()


def test_brief_api_principal_tenant_idempotency_and_canary(client):
    cleanup()
    try:
        task=AipTaskStore().create_task(ORG,ACTOR,f"api-task-{uuid.uuid4().hex}",CreateTaskRequest(title="W2A API authority"))
        payload={"taskId":task.id,"briefType":"ecommerce.analysis","schemaRef":{"resourceType":"Schema","resourceId":"analysis","revision":"1","authority":"aip"},"spec":{"goal":"facts first"}}
        key=f"api-brief-{uuid.uuid4().hex}"
        created=client.post("/v1/aip/production-contracts/task-briefs",headers=headers(key=key),json=payload)
        assert created.status_code==201,created.text
        body=created.json(); assert body["tenant"]=={"orgId":"org-org","projectId":"dev-project"}; assert body["lifecycle"]=="draft"
        listing=client.get("/v1/aip/production-contracts/task-briefs",headers=headers())
        assert listing.status_code==200 and any(item["briefId"]==body["briefId"] for item in listing.json()["items"])
        canary_listing=client.get("/v1/aip/production-contracts/task-briefs",headers=headers("dev-org"))
        assert canary_listing.status_code==200,canary_listing.text
        assert all(item["briefId"]!=body["briefId"] for item in canary_listing.json()["items"])
        assert client.post("/v1/aip/production-contracts/task-briefs",headers=headers(key=key),json=payload).json()["briefId"]==body["briefId"]
        assert client.get(f"/v1/aip/production-contracts/task-briefs/{body['briefId']}",headers=headers("dev-org")).status_code==404
        frozen=client.post(f"/v1/aip/production-contracts/task-briefs/{body['briefId']}/freeze",headers=headers(key=f"freeze-{uuid.uuid4().hex}"),json={"expectedVersion":1})
        assert frozen.status_code==200 and frozen.json()["revision"]==2 and frozen.json()["lifecycle"]=="frozen"
        stale=client.post(f"/v1/aip/production-contracts/task-briefs/{body['briefId']}/freeze",headers=headers(key=f"freeze-{uuid.uuid4().hex}"),json={"expectedVersion":1})
        assert stale.status_code==409 and stale.json()["code"]=="AIP_VERSION_CONFLICT"
    finally:cleanup()


def test_evidence_bundle_api_binds_exact_frozen_brief_and_evidence(client):
    cleanup()
    try:
        task=AipTaskStore().create_task(ORG,ACTOR,f"api-task-{uuid.uuid4().hex}",CreateTaskRequest(title="W2A API evidence authority"))
        created=client.post(
            "/v1/aip/production-contracts/task-briefs",
            headers=headers(key=f"brief-{uuid.uuid4().hex}"),
            json={
                "taskId":task.id,
                "briefType":"ecommerce.analysis",
                "schemaRef":{"resourceType":"Schema","resourceId":"analysis","revision":"1","authority":"aip"},
                "spec":{"goal":"bind exact real evidence"},
            },
        )
        assert created.status_code==201,created.text
        draft=created.json()
        frozen_response=client.post(
            f"/v1/aip/production-contracts/task-briefs/{draft['briefId']}/freeze",
            headers=headers(key=f"freeze-{uuid.uuid4().hex}"),
            json={"expectedVersion":draft["version"]},
        )
        assert frozen_response.status_code==200,frozen_response.text
        frozen=frozen_response.json()
        evidence_id=f"ev-api-{uuid.uuid4().hex[:18]}"
        evidence_hash="c"*64
        with connect(ORG) as conn:
            conn.execute(
                """INSERT INTO aip_evidence(org_id,project_id,evidence_id,evidence_type,subject_ref,source_type,source_ref,observed_at,freshness_at,content_hash,payload,created_by)
                VALUES(%s,%s,%s,'order_fact','{}','database','w2a-api-real-order',NOW(),NOW(),%s,%s::jsonb,%s)""",
                (*ORG.key,evidence_id,evidence_hash,'{"factIds":["order_snapshot"]}',EVIDENCE_ACTOR),
            )
            conn.commit()
        payload={
            "briefRef":{"resourceType":"TaskBriefRevision","resourceId":frozen["briefId"],"revision":frozen["revision"],"contentHash":frozen["contentHash"]},
            "subjectRefs":[],
            "cutoffAt":(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            "itemRefs":[{"resourceType":"Evidence","resourceId":evidence_id,"revision":1,"contentHash":evidence_hash}],
            "requiredFactIds":["order_snapshot","customer_profile"],
            "marking":["public"],
            "licenseSummary":{"source":"authorized database"},
        }
        key=f"bundle-{uuid.uuid4().hex}"
        forged={**payload,"coverage":"complete","missing":[],"freshness":"fresh"}
        assert client.post("/v1/aip/production-contracts/evidence-bundles/build",headers=headers(key=f"forge-{uuid.uuid4().hex}"),json=forged).status_code in (400, 422)
        response=client.post("/v1/aip/production-contracts/evidence-bundles/build",headers=headers(key=key),json=payload)
        assert response.status_code==201,response.text
        bundle=response.json()
        assert bundle["itemRefs"][0]["resourceId"]==evidence_id
        assert bundle["coverage"]=="partial"
        assert bundle["missing"]==[{"factId":"customer_profile"}]
        listing=client.get("/v1/aip/production-contracts/evidence-bundles",headers=headers())
        assert listing.status_code==200 and any(item["bundleId"]==bundle["bundleId"] for item in listing.json()["items"])
        canary_listing=client.get("/v1/aip/production-contracts/evidence-bundles",headers=headers("dev-org"))
        assert canary_listing.status_code==200,canary_listing.text
        assert all(item["bundleId"]!=bundle["bundleId"] for item in canary_listing.json()["items"])
        assert client.post("/v1/aip/production-contracts/evidence-bundles/build",headers=headers(key=key),json=payload).json()["bundleId"]==bundle["bundleId"]
        assert client.get(f"/v1/aip/production-contracts/evidence-bundles/{bundle['bundleId']}",headers=headers()).status_code==200
        assert client.get(f"/v1/aip/production-contracts/evidence-bundles/{bundle['bundleId']}",headers=headers("dev-org")).status_code==404
    finally:
        cleanup()


def test_brief_api_requires_idempotency_key(client):
    response=client.post("/v1/aip/production-contracts/task-briefs",headers=headers(),json={})
    assert response.status_code==400
    assert response.json()["code"]=="VALIDATION"
    assert any(error["loc"]==["header","Idempotency-Key"] for error in response.json()["details"]["errors"])

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from aos_api.aip_contracts import ResourceRef
from aos_api.aip_production_contract_store import (
    AipProductionContractStore, ProductionContractDependencyBlocked,
    ProductionContractIdempotencyConflict, ProductionContractNotFound,
)
from aos_api.aip_production_contracts import (
    BriefLifecycle, Coverage, CreateBriefRequest, CreateEvidenceBundleRequest,
    ExactRevisionRef, Freshness,
)
from aos_api.aip_task_models import CreateTaskRequest
from aos_api.aip_task_store import AipTaskStore
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

ORG = TenantScope("org-org", "dev-project")
CANARY = TenantScope("dev-org", "dev-project")
ACTOR = "test:w2a"


def cleanup() -> None:
    with connect(ORG) as conn:
        task_ids = [r["task_id"] for r in conn.execute(
            "SELECT task_id FROM aip_task WHERE org_id=%s AND project_id=%s AND created_by=%s AND title LIKE 'W2A %%'",
            (*ORG.key, ACTOR),
        ).fetchall()]
        conn.execute("DELETE FROM aip_production_contract_receipt WHERE org_id=%s AND project_id=%s AND created_by=%s", (*ORG.key, ACTOR))
        conn.execute("DELETE FROM aip_evidence_bundle_revision WHERE org_id=%s AND project_id=%s AND created_by=%s", (*ORG.key, ACTOR))
        conn.execute("DELETE FROM aip_task_brief_revision WHERE org_id=%s AND project_id=%s AND created_by=%s", (*ORG.key, ACTOR))
        for task_id in task_ids:
            conn.execute("DELETE FROM aip_task_brief_head WHERE org_id=%s AND project_id=%s AND task_id=%s", (*ORG.key, task_id))
        conn.execute("DELETE FROM aip_evidence WHERE org_id=%s AND project_id=%s AND created_by=%s AND source_ref='real-order'", (*ORG.key, ACTOR))
        for task_id in task_ids:
            conn.execute("DELETE FROM aip_task WHERE org_id=%s AND project_id=%s AND task_id=%s", (*ORG.key, task_id))
        conn.commit()


@pytest.fixture(autouse=True)
def isolated_w2a_rows():
    cleanup()
    yield
    cleanup()


def key(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def test_brief_freeze_is_append_only_and_tenant_isolated() -> None:
    task = AipTaskStore().create_task(ORG, ACTOR, key("task"), CreateTaskRequest(title="W2A real contract test"))
    store = AipProductionContractStore()
    body = CreateBriefRequest(task_id=task.id, brief_type="ecommerce.analysis", schema_ref=ResourceRef(resource_type="Schema",resource_id="ecommerce.analysis",revision="1",authority="aip"), spec={"goal":"analyse real orders"})
    brief = store.create_brief(ORG,ACTOR,key("brief"),body)
    frozen = store.freeze_brief(ORG,ACTOR,brief.brief_id,brief.version,key("freeze"))
    assert brief.revision == 1 and brief.lifecycle == BriefLifecycle.DRAFT
    assert frozen.revision == 2 and frozen.lifecycle == BriefLifecycle.FROZEN
    assert frozen.content_hash == brief.content_hash and frozen.version == 2
    assert store.get_brief(ORG,brief.brief_id,1).lifecycle == BriefLifecycle.DRAFT
    with pytest.raises(ProductionContractNotFound): store.get_brief(CANARY,brief.brief_id)


def test_brief_create_replays_and_rejects_payload_drift() -> None:
    task=AipTaskStore().create_task(ORG,ACTOR,key("task"),CreateTaskRequest(title="W2A idempotency")); store=AipProductionContractStore(); idem=key("brief")
    body=CreateBriefRequest(task_id=task.id,brief_type="ecommerce.analysis",schema_ref=ResourceRef(resource_type="Schema",resource_id="analysis",revision="1",authority="aip"),spec={"a":1})
    assert store.create_brief(ORG,ACTOR,idem,body).brief_id == store.create_brief(ORG,ACTOR,idem,body).brief_id
    with pytest.raises(ProductionContractIdempotencyConflict):
        store.create_brief(ORG,ACTOR,idem,body.model_copy(update={"spec":{"a":2}}))


def test_bundle_accepts_only_exact_frozen_evidence_refs() -> None:
    task=AipTaskStore().create_task(ORG,ACTOR,key("task"),CreateTaskRequest(title="W2A evidence")); store=AipProductionContractStore()
    draft=store.create_brief(ORG,ACTOR,key("brief"),CreateBriefRequest(task_id=task.id,brief_type="ecommerce.analysis",schema_ref=ResourceRef(resource_type="Schema",resource_id="analysis",revision="1",authority="aip"),spec={"goal":"facts first"}))
    frozen=store.freeze_brief(ORG,ACTOR,draft.brief_id,draft.version,key("freeze"))
    evidence_id=f"ev-{uuid.uuid4().hex[:18]}"; evidence_hash="a"*64
    with connect(ORG) as conn:
        conn.execute("""INSERT INTO aip_evidence(org_id,project_id,evidence_id,evidence_type,subject_ref,source_type,source_ref,observed_at,freshness_at,content_hash,created_by)
            VALUES(%s,%s,%s,'order_fact','{}','database','real-order',NOW(),NOW(),%s,%s)""",(*ORG.key,evidence_id,evidence_hash,ACTOR)); conn.commit()
    req=CreateEvidenceBundleRequest(brief_ref=ExactRevisionRef(resource_type="TaskBriefRevision",resource_id=frozen.brief_id,revision=frozen.revision,content_hash=frozen.content_hash),subject_refs=[],cutoff_at=datetime.now(timezone.utc),item_refs=[ExactRevisionRef(resource_type="Evidence",resource_id=evidence_id,revision=1,content_hash=evidence_hash)],coverage=Coverage.PARTIAL,missing=[{"fact":"customer_profile"}],freshness=Freshness.FRESH)
    bundle=store.create_evidence_bundle(ORG,ACTOR,key("bundle"),req)
    assert bundle.coverage == Coverage.PARTIAL and bundle.lifecycle == BriefLifecycle.FROZEN
    with pytest.raises(ProductionContractDependencyBlocked):
        store.create_evidence_bundle(ORG,ACTOR,key("bundle"),req.model_copy(update={"item_refs":[ExactRevisionRef(resource_type="Evidence",resource_id=evidence_id,revision=1,content_hash="b"*64)]}))

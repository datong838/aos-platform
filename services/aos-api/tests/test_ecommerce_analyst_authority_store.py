from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime

import pytest

from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef, GrowthPlanRevision
from aos_api.ecommerce_analyst_authority_store import AnalystAuthorityConflict, AnalystAuthorityIdempotencyConflict, AnalystAuthorityNotFound, EcommerceAnalystAuthorityStore
from aos_api.tenant_scope import TenantScope

NOW = datetime(2026, 8, 25, tzinfo=UTC)
HASH = "a" * 64
SCOPE = TenantScope(org_id="org-org", project_id="dev-project")


class Cursor:
    def __init__(self, row=None, rowcount=1): self.row = row; self.rowcount = rowcount
    def fetchone(self): return self.row


class Connection:
    def __init__(self, rows=()): self.rows = list(rows); self.calls = []; self.commits = 0
    def execute(self, sql, params=None):
        normalized = " ".join(sql.split()); self.calls.append((normalized, params))
        row = self.rows.pop(0) if normalized.startswith("SELECT") else None
        return Cursor(row)
    def commit(self): self.commits += 1


def factory(connection):
    @contextmanager
    def connect(scope): assert scope == SCOPE; yield connection
    return connect


def exact(kind, identity): return {"resourceType": kind, "resourceId": identity, "revision": 1, "contentHash": HASH}


def plan(org="org-org") -> GrowthPlanRevision:
    return GrowthPlanRevision.model_validate({"tenant": {"orgId": org, "projectId": "dev-project"}, "planId": "plan-1", "revision": 1, "version": 1, "lifecycle": "approved", "decisionRef": exact("DecisionSummaryRevision", "decision-1"), "objective": "grow", "constraints": [], "budget": "10", "expectedEffect": "+1%", "confidence": 0.5, "stopConditions": ["stale"], "items": [{"itemId": "a", "taskType": "analysis", "title": "A", "objective": "A"}], "approvedAt": NOW, "contentHash": HASH, "createdBy": "user:operator", "createdAt": NOW})


def test_publish_plan_writes_head_revision_receipt_and_commits() -> None:
    connection = Connection(rows=[None, None])
    result = EcommerceAnalystAuthorityStore(factory(connection)).publish_plan(SCOPE, "user:operator", "key-1", plan(), expected_version=0)
    assert result.resource_type == "GrowthPlanRevision" and connection.commits == 1
    sql = "\n".join(statement for statement, _ in connection.calls)
    assert "INSERT INTO ecommerce_analyst_growth_plan_head" in sql
    assert "INSERT INTO ecommerce_analyst_growth_plan_revision" in sql
    assert "INSERT INTO ecommerce_analyst_authority_receipt" in sql


def test_publish_plan_enforces_cas_idempotency_tenant_and_actor() -> None:
    stale = Connection(rows=[None, {"current_revision": 1, "version": 1}])
    with pytest.raises(AnalystAuthorityConflict, match="stale"):
        EcommerceAnalystAuthorityStore(factory(stale)).publish_plan(SCOPE, "user:operator", "key", plan(), expected_version=0)
    replay = Connection(rows=[{"request_hash": "b" * 64, "result_ref": exact("GrowthPlanRevision", "plan-1")}])
    with pytest.raises(AnalystAuthorityIdempotencyConflict):
        EcommerceAnalystAuthorityStore(factory(replay)).publish_plan(SCOPE, "user:operator", "key", plan(), expected_version=0)
    untouched = Connection()
    store = EcommerceAnalystAuthorityStore(factory(untouched))
    with pytest.raises(AnalystAuthorityConflict, match="tenant"):
        store.publish_plan(SCOPE, "user:operator", "key", plan("dev-org"), expected_version=0)
    with pytest.raises(AnalystAuthorityConflict, match="actor"):
        store.publish_plan(SCOPE, "user:other", "key", plan(), expected_version=0)
    assert untouched.calls == []


def test_plan_exact_ref_rejects_payload_hash_drift_and_receipt_is_scope_bound() -> None:
    payload = plan().model_dump(mode="json", by_alias=True)
    drifted = {**payload, "contentHash": "b" * 64}
    connection = Connection(rows=[{"payload": drifted, "content_hash": HASH}])
    with pytest.raises(AnalystAuthorityNotFound, match="payload hash"):
        EcommerceAnalystAuthorityStore(factory(connection)).get_plan_exact(
            SCOPE,
            AnalystExactRef.model_validate(exact("GrowthPlanRevision", "plan-1")),
        )

    receipt = Connection(rows=[{"result_ref": exact("GrowthPlanRevision", "plan-1")}])
    result = EcommerceAnalystAuthorityStore(factory(receipt)).find_plan_publication_receipt(
        SCOPE, "approval-key"
    )
    assert result is not None and result.resource_id == "plan-1"
    assert receipt.calls[0][1] == (
        "org-org",
        "dev-project",
        "analyst.growth_plan_publish",
        "approval-key",
    )

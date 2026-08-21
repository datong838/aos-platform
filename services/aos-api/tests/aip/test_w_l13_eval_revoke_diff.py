"""W-L13 Eval publication revoke propagation + semantic Diff."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from aos_api.aip_production_contract_store import (
    AipProductionContractStore,
    ProductionContractDependencyBlocked,
    canonical_hash,
)
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope
from test_w2b_production_contract_store import (
    SCOPE as W2B,
    _eval_request,
    _seed_dependencies,
)
from aos_api.aip_production_contracts import ReviseEvalContractRequest

ORG = TenantScope("org-org", "dev-project")
HASH = "a" * 64
NOW = datetime(2026, 8, 20, 5, 0, tzinfo=timezone.utc)


def _seed_publication_bound_contract() -> tuple[str, str, str]:
    suffix = uuid.uuid4().hex[:12]
    contract_id = f"eval-l13-{suffix}"
    publication_id = f"pub-l13-{suffix}"
    published_event = f"pub-evt-{suffix}"
    gate_id = f"gate-l13-{suffix}"
    suite_id = f"suite-l13-{suffix}"
    run_id = f"run-l13-{suffix}"
    with connect(ORG) as conn:
        conn.execute(
            """INSERT INTO aip_eval_suite_revision
               (org_id,project_id,suite_id,revision,content_hash,target_ref,dataset_ref,
                judge_ref,cases,gate_threshold,actor)
               VALUES(%s,%s,%s,1,%s,'{}','{}','{}','[{}]',1.0,'test')
               ON CONFLICT DO NOTHING""",
            (*ORG.key, suite_id, HASH),
        )
        conn.execute(
            """INSERT INTO aip_eval_run
               (org_id,project_id,run_id,suite_id,suite_revision,suite_hash,target_ref,
                dataset_ref,judge_ref,status,idempotency_key,version,created_by,created_at)
               VALUES(%s,%s,%s,%s,1,%s,'{}'::jsonb,'{}'::jsonb,'{}'::jsonb,'succeeded',
                      %s,1,'test',%s)
               ON CONFLICT DO NOTHING""",
            (*ORG.key, run_id, suite_id, HASH, f"idem-{suffix}", NOW),
        )
        conn.execute(
            """INSERT INTO aip_release_gate_decision
               (org_id,project_id,decision_id,target_ref,suite_ref,eval_run_id,
                eval_report_ref,status,decision_hash,decided_by,decided_at,expires_at)
               VALUES(%s,%s,%s,'{}'::jsonb,'{}'::jsonb,%s,'{}'::jsonb,'passed',%s,
                      'test',%s,%s)""",
            (*ORG.key, gate_id, run_id, HASH, NOW, NOW + timedelta(days=30)),
        )
        conn.execute(
            """INSERT INTO aip_publication_event
               (org_id,project_id,event_id,publication_id,target_ref,event_type,
                release_gate_decision_id,reason_hash,actor,occurred_at)
               VALUES(%s,%s,%s,%s,'{}'::jsonb,'published',%s,%s,'test',%s)""",
            (*ORG.key, published_event, publication_id, gate_id, HASH, NOW),
        )
        row = conn.execute(
            """SELECT * FROM aip_publication_event
               WHERE org_id=%s AND project_id=%s AND event_id=%s""",
            (*ORG.key, published_event),
        ).fetchone()
        event_hash = canonical_hash(AipProductionContractStore._publication_snapshot(row))
        suite_ref = {
            "resourceType": "EvalSuiteRevision",
            "resourceId": suite_id,
            "revision": 1,
            "contentHash": HASH,
        }
        publication_ref = {
            "resourceType": "PublicationEvent",
            "resourceId": published_event,
            "revision": 1,
            "contentHash": event_hash,
        }
        gate_ref = {
            "resourceType": "ReleaseGateDecision",
            "resourceId": gate_id,
            "revision": 1,
            "contentHash": HASH,
        }
        payload = {
            "suiteRef": suite_ref,
            "publicationRef": publication_ref,
            "releaseGateRef": gate_ref,
            "artifactSchemaRef": {
                "resourceType": "Schema",
                "resourceId": "artifact",
                "revision": "1",
                "authority": "aip",
            },
            "severityThresholds": {"critical": 1.0},
            "gatePolicy": {"mode": "all"},
            "returnMapping": {},
            "overridePolicy": {"allowed": False},
        }
        contract_hash = canonical_hash(payload)
        conn.execute(
            """INSERT INTO aip_eval_contract_head
               (org_id,project_id,contract_id,current_revision,version)
               VALUES(%s,%s,%s,1,1)""",
            (*ORG.key, contract_id),
        )
        conn.execute(
            """INSERT INTO aip_eval_contract_revision
               (org_id,project_id,contract_id,revision,suite_ref,publication_ref,
                release_gate_ref,artifact_schema_ref,severity_thresholds,gate_policy,
                return_mapping,override_policy,content_hash,lifecycle,created_by)
               VALUES(%s,%s,%s,1,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
                      %s::jsonb,%s::jsonb,%s::jsonb,%s,'frozen','test')""",
            (
                *ORG.key,
                contract_id,
                json.dumps(suite_ref),
                json.dumps(publication_ref),
                json.dumps(gate_ref),
                json.dumps(payload["artifactSchemaRef"]),
                json.dumps(payload["severityThresholds"]),
                json.dumps(payload["gatePolicy"]),
                json.dumps(payload["returnMapping"]),
                json.dumps(payload["overridePolicy"]),
                contract_hash,
            ),
        )
        conn.commit()
    return contract_id, publication_id, gate_id


def test_publication_revoke_blocks_eval_contract_readiness() -> None:
    contract_id, publication_id, gate_id = _seed_publication_bound_contract()
    store = AipProductionContractStore()
    ready = store.get_eval_contract(ORG, contract_id, 1)
    assert ready.readiness.value == "ready"
    assert not any(item.code == "EVAL_PUBLICATION_REVOKED" for item in ready.blockers)
    with connect(ORG) as conn:
        conn.execute(
            """INSERT INTO aip_publication_event
               (org_id,project_id,event_id,publication_id,target_ref,event_type,
                release_gate_decision_id,reason_hash,actor,occurred_at)
               VALUES(%s,%s,%s,%s,'{}'::jsonb,'revoked',%s,%s,'test',%s)""",
            (
                *ORG.key,
                f"rev-{uuid.uuid4().hex[:12]}",
                publication_id,
                gate_id,
                "b" * 64,
                NOW + timedelta(hours=1),
            ),
        )
        conn.commit()
    blocked = store.get_eval_contract(ORG, contract_id, 1)
    assert blocked.readiness.value == "blocked"
    assert any(item.code == "EVAL_PUBLICATION_REVOKED" for item in blocked.blockers)


def test_eval_contract_semantic_diff() -> None:
    _seed_dependencies()

    class ReadyStore(AipProductionContractStore):
        def _eval_blockers(self, conn, scope, row):  # type: ignore[no-untyped-def]
            return []

    store = ReadyStore()
    created = store.create_eval_contract(W2B, "test", f"diff-{uuid.uuid4().hex}", _eval_request())
    revised = store.revise_eval_contract(
        W2B,
        "test",
        created.contract_id,
        f"diff-rev-{uuid.uuid4().hex}",
        ReviseEvalContractRequest(
            expected_version=1,
            suite_ref=created.suite_ref,
            artifact_schema_ref=created.artifact_schema_ref,
            severity_thresholds={"critical": 1.0, "warning": 0.5},
            gate_policy={"mode": "any"},
            return_mapping={"critical": "draft"},
            override_policy={"allowed": False},
        ),
    )
    diff = store.diff_eval_contract(W2B, created.contract_id, 1, revised.revision)
    assert diff.change_count >= 1
    assert "语义变更" in diff.summary
    labels = {item.label for item in diff.changes}
    assert "严重级别阈值" in labels or "门禁策略" in labels
    with pytest.raises(ProductionContractDependencyBlocked):
        store.diff_eval_contract(W2B, created.contract_id, 1, 1)

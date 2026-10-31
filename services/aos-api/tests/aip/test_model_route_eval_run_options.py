from __future__ import annotations

from datetime import UTC, datetime

import pytest
from psycopg.rows import dict_row

from aos_api.aip_model_route_eval_run_options import list_route_eval_run_options
from aos_api.aip_model_runtime_contracts import ModelEvalCandidate
from aos_api.tenant_scope import TenantScope


HASH = {
    key: char * 64
    for key, char in {
        "source": "a", "target": "b", "suite": "c", "dataset": "d",
        "dataset_source": "e", "redaction": "f", "judge": "1",
        "judge_model": "2", "contract": "3",
    }.items()
}


def candidate() -> ModelEvalCandidate:
    return ModelEvalCandidate(
        sourceRef={"assetType": "ModelRouteRevision", "assetId": "qyh-route", "revision": 8, "contentHash": HASH["source"]},
        targetRef={"assetType": "ModelRouteRevision", "assetId": "qyh-route", "revision": 9, "contentHash": HASH["target"]},
        expectedHeadVersion=8,
        sourceLifecycle="draft",
        executionAllowed=False,
    )


def row(run_id: str, *, status: str = "queued", target_hash: str | None = None):
    return {
        "org_id": "org-org", "project_id": "dev-project", "run_id": run_id,
        "suite_id": "suite-1", "suite_revision": 1, "suite_hash": HASH["suite"],
        "eval_contract_ref": {"resourceType": "EvalContractRevision", "resourceId": "contract-1", "revision": 3, "contentHash": HASH["contract"]},
        "subject_artifact_ref": None, "stage_attempt_ref": None, "gate_policy_ref": None, "evidence_cutoff_at": None,
        "target_ref": {"assetType": "model_route", "assetId": "qyh-route", "revision": "9", "contentHash": target_hash or HASH["target"]},
        "dataset_ref": {"datasetId": "dataset-1", "revision": 1, "contentHash": HASH["dataset"], "sourceHash": HASH["dataset_source"], "redactionPolicy": {"assetType": "policy", "assetId": "redact-1", "revision": "1", "contentHash": HASH["redaction"]}},
        "judge_ref": {"judgeId": "judge-1", "revision": 1, "contentHash": HASH["judge"], "modelRoute": {"assetType": "registered_model", "assetId": "judge-model", "revision": "2", "contentHash": HASH["judge_model"]}},
        "status": status, "idempotency_key": f"key-{run_id}", "created_by": "human",
        "created_at": datetime(2026, 10, 31, 8, 0, tzinfo=UTC), "started_at": None, "finished_at": None, "version": 1,
    }


class Result:
    def __init__(self, *, one=None, many=None):
        self.one, self.many = one, many

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class Connection:
    autocommit = False

    class Info:
        dbname = "aos_meta_head"
        transaction_status = 2

    info = Info()

    def __init__(self, rows):
        self.rows = rows
        self.row_factory = dict_row
        self.calls = []
        self.evaluated_at = datetime(2026, 10, 31, 8, 30, tzinfo=UTC)

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        if "transaction_timestamp() AS evaluated_at" in sql:
            return Result(one={"role": "aos_runtime", "database": "aos_meta_head", "org_id": "org-org", "project_id": "dev-project", "isolation": "repeatable read", "read_only": "on", "evaluated_at": self.evaluated_at})
        return Result(many=self.rows)


def test_lists_only_exact_live_contracted_route_runs_in_one_readonly_snapshot():
    conn = Connection([row("run-new", status="running"), row("run-old")])
    result = list_route_eval_run_options(
        conn, expected_database="aos_meta_head", scope=TenantScope("org-org", "dev-project"),
        candidate=candidate(), limit=20,
    )
    assert [item.run_id for item in result] == ["run-new", "run-old"]
    sql, params = conn.calls[1]
    assert "status IN ('queued','running')" in sql
    assert "eval_contract_ref IS NOT NULL" in sql
    assert "target_ref=%s::jsonb" in sql
    assert "ORDER BY created_at DESC,run_id ASC LIMIT %s" in sql
    assert params[:2] == ("org-org", "dev-project")
    assert params[-1] == 20
    assert len(conn.calls) == 3


def test_rejects_candidate_or_persisted_row_drift_instead_of_returning_partial_options():
    conn = Connection([row("run-drift", target_hash="9" * 64)])
    with pytest.raises(ValueError):
        list_route_eval_run_options(
            conn, expected_database="aos_meta_head", scope=TenantScope("org-org", "dev-project"),
            candidate=candidate(), limit=20,
        )
    model_candidate = candidate().model_copy(update={
        "source_ref": candidate().source_ref.model_copy(update={"asset_type": "RegisteredModelRevision"}),
        "target_ref": candidate().target_ref.model_copy(update={"asset_type": "RegisteredModelRevision"}),
    })
    with pytest.raises(ValueError):
        list_route_eval_run_options(
            Connection([]), expected_database="aos_meta_head", scope=TenantScope("org-org", "dev-project"),
            candidate=model_candidate, limit=20,
        )


@pytest.mark.parametrize("limit", [0, 21, True])
def test_rejects_noncanonical_limit(limit):
    with pytest.raises(ValueError):
        list_route_eval_run_options(
            Connection([]), expected_database="aos_meta_head", scope=TenantScope("org-org", "dev-project"),
            candidate=candidate(), limit=limit,
        )

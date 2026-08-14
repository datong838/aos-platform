from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime

import pytest

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_eval_contracts import EvidenceQuality
from aos_api.aip_memory_improvement import (
    AipMemoryImprovementConflict,
    AipMemoryImprovementService,
    ImprovementEvaluationRequest,
    TrustedImprovementEvidence,
)
from aos_api.aip_memory_projection_contracts import ImprovementMetric
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 8, 15, 8, tzinfo=UTC)
HASH_A, HASH_B, HASH_C = "a" * 64, "b" * 64, "c" * 64


def ref(kind: str, identifier: str, revision: int = 1, content_hash: str = HASH_A):
    return VersionedAssetRef(
        asset_type=kind, asset_id=identifier, revision=revision, content_hash=content_hash
    )


def request(observation_id: str = "obs-1") -> ImprovementEvaluationRequest:
    return ImprovementEvaluationRequest(
        observation_id=observation_id,
        agent_instance_ref=ref("AgentInstance", "data-advisor"),
        metric_definition_ref=ref("MetricDefinition", "task-quality", content_hash=HASH_B),
        eval_contract_ref=ref("EvalContract", "e7-eval", content_hash=HASH_C),
        cutoff_at=NOW,
        observed_at=NOW,
    )


class Result:
    def __init__(self, row=None, rows=None):
        self._row = row
        self._rows = rows or []

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._rows


class FakeConn:
    def __init__(self):
        self.rows = {}
        self.scopes = []
        self.commits = 0

    def execute(self, sql, params):
        normalized = " ".join(sql.split())
        self.scopes.append(tuple(params[:2]))
        if "FROM aip_agent_instance" in normalized:
            return Result({"version": 1, "content_hash": HASH_A, "status": "active"})
        if "FROM aip_metric_definition_revision" in normalized:
            return Result({"content_hash": HASH_B})
        if "FROM aip_eval_contract_revision" in normalized:
            return Result({"content_hash": HASH_C, "lifecycle": "frozen"})
        if normalized.startswith("SELECT * FROM aip_memory_improvement_observation"):
            if "ORDER BY" in normalized:
                return Result(rows=list(self.rows.values()))
            return Result(self.rows.get(params[2]))
        if normalized.startswith("INSERT INTO aip_memory_improvement_observation"):
            keys = (
                "org_id", "project_id", "observation_id", "instance_id",
                "instance_version", "instance_hash", "metric_definition_ref",
                "eval_contract_ref", "eval_report_ref", "baseline_cohort_ref",
                "treatment_cohort_ref", "exposure_refs", "metrics", "quality",
                "source_refs", "cutoff_at", "observed_at", "conclusion",
                "limitations", "observation_hash",
            )
            self.rows[params[2]] = dict(zip(keys, params, strict=True))
            return Result()
        raise AssertionError(normalized)

    def commit(self):
        self.commits += 1


def service(conn: FakeConn):
    @contextmanager
    def connect(_scope):
        yield conn

    return AipMemoryImprovementService(connect)


def governed(metric: ImprovementMetric) -> TrustedImprovementEvidence:
    return TrustedImprovementEvidence(
        eval_report_ref=ref("EvalReport", "report"),
        baseline_cohort_ref=ref("CohortSnapshot", "baseline"),
        treatment_cohort_ref=ref("CohortSnapshot", "treatment"),
        exposure_refs=[ref("MemoryExposure", "exp-1")],
        metrics=[metric],
        quality=EvidenceQuality.MEASURED,
        source_refs=[ref("EvalReport", "report")],
    )


def test_missing_governed_comparison_appends_unknown_without_invented_metrics() -> None:
    conn = FakeConn()
    observation = service(conn).evaluate(SCOPE, request())
    assert observation.conclusion == "insufficient_evidence"
    assert observation.quality == "unknown"
    assert observation.metrics == observation.source_refs == observation.exposure_refs == []
    assert observation.limitations == ["comparable_governed_evidence_unavailable"]
    assert conn.rows["obs-1"]["eval_report_ref"] is None
    assert conn.rows["obs-1"]["baseline_cohort_ref"] is None
    assert conn.rows["obs-1"]["treatment_cohort_ref"] is None
    assert set(conn.scopes) == {SCOPE.key}
    assert conn.commits == 1


def test_minimum_sample_gate_discards_untrusted_positive_signal() -> None:
    metric = ImprovementMetric(
        metric_name="task_success_rate", baseline_value=0.4, treatment_value=0.9,
        baseline_sample_size=29, treatment_sample_size=30,
    )
    observation = service(FakeConn()).evaluate(SCOPE, request(), evidence=governed(metric))
    assert observation.conclusion == "insufficient_evidence"
    assert observation.quality == "unknown"
    assert observation.metrics == []
    assert "minimum_sample_size_not_met" in observation.limitations


def test_sufficient_server_resolved_evidence_can_report_improved() -> None:
    metric = ImprovementMetric(
        metric_name="human_edit_rate", baseline_value=0.7, treatment_value=0.2,
        baseline_sample_size=30, treatment_sample_size=31,
        confidence_interval_lower=-0.7, confidence_interval_upper=-0.3,
    )
    observation = service(FakeConn()).evaluate(SCOPE, request(), evidence=governed(metric))
    assert observation.conclusion == "improved"
    assert observation.quality == "measured"
    assert observation.metrics[0].metric_name == "human_edit_rate"


def test_exact_replay_is_idempotent_but_hash_drift_conflicts() -> None:
    conn = FakeConn()
    evaluator = service(conn)
    first = evaluator.evaluate(SCOPE, request())
    assert evaluator.evaluate(SCOPE, request()).observation_hash == first.observation_hash
    drifted = request()
    drifted.observed_at = datetime(2026, 8, 15, 9, tzinfo=UTC)
    with pytest.raises(AipMemoryImprovementConflict):
        evaluator.evaluate(SCOPE, drifted)


def test_observation_list_remains_tenant_scoped() -> None:
    conn = FakeConn()
    evaluator = service(conn)
    evaluator.evaluate(SCOPE, request())
    items = evaluator.list_observations(SCOPE, instance_id="data-advisor")
    assert len(items) == 1
    assert items[0].tenant.org_id == "org-org"
    assert set(conn.scopes) == {SCOPE.key}

"""Installed snapshot evaluation; synthetic input is not installation authority."""
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from aos_api.source_readiness import SourceReadinessService
from aos_api.source_readiness_contracts import CANONICAL_QYH_SOURCES
from aos_api.source_readiness_snapshot_contracts import (
    InstalledSnapshotReadinessInput, SNAPSHOT_REF_TYPES,
)

NOW = datetime(2026, 9, 14, 12, tzinfo=UTC)


def payload():
    tenant = dict(org_id="org-org", project_id="dev-project")
    sources = []
    for canonical in CANONICAL_QYH_SOURCES:
        refs = {key: dict(resource_type=value, resource_id=key, revision="1",
                         content_hash="a" * 64, authority="fixture:owner")
                for key, value in SNAPSHOT_REF_TYPES.items()}
        sources.append(dict(tenant=tenant.copy(), source_id="niushop-qyh",
            pipeline_id=canonical.pipeline_id, object_type=canonical.object_type,
            observed_at=NOW - timedelta(seconds=2),
            freshness_expires_at=NOW + timedelta(hours=1), **refs,
            latest_run=dict(run_id=canonical.pipeline_id, status="succeeded",
                            finished_at=NOW - timedelta(seconds=1)),
            counts=dict(source_total=1, source_active=1, source_deleted=0,
                        projection_total=1, unexplained_delta=0),
            quality=dict(status="pass", rule_ref=refs["quality_policy_ref"])))
    return dict(tenant=tenant, checked_at=NOW, cutoff_at=NOW-timedelta(seconds=1), sources=sources)


def evaluate(data):
    return SourceReadinessService.evaluate_installed_snapshot(
        InstalledSnapshotReadinessInput.model_validate(data))


def test_complete_canonical_set_preserves_observation_cutoff():
    result = evaluate(payload())
    assert result.status == "ready" and len(result.sources) == 12
    assert result.cutoff_at < result.checked_at
    assert all(s.data_cutoff == result.cutoff_at for s in result.sources)
    assert result.receipt_ref is None
    assert all(s.projected_at is None for s in result.sources)


@pytest.mark.parametrize("change,expected", [
    ({"freshness_expires_at": NOW}, "stale"),
    ({"freshness_expires_at": NOW-timedelta(seconds=1)}, "stale"),
    ({"freshness_expires_at": None}, "unknown"),
    ({"mapping_ref": None}, "blocked"),
    ({"latest_run": {"status": "failed"}}, "failed"),
    ({"latest_run": {"status": "running"}}, "unknown"),
    ({"counts": {"source_total": 0, "projection_total": 0, "unexplained_delta": 0}}, "empty"),
    ({"counts": {"source_total": 1, "projection_total": 2, "unexplained_delta": 0}}, "failed"),
    ({"counts": {}}, "failed"),
])
def test_fail_closed_status(change, expected):
    data = payload()
    data["sources"][0].update(change)
    assert evaluate(data).status == expected


@pytest.mark.parametrize("status,expected", [("fail", "failed"), ("unknown", "unknown")])
def test_original_quality_result_is_not_metadata_pass(status, expected):
    data = payload()
    data["sources"][0]["quality"]["status"] = status
    assert evaluate(data).status == expected


@pytest.mark.parametrize("fault", ["missing", "duplicate", "order", "object", "tenant",
    "naive", "future", "ref", "rule", "status", "counts", "run_time", "run_missing"])
def test_rejects_inconsistent_input(fault):
    data = payload()
    s = data["sources"][0]
    if fault == "missing": data["sources"].pop()
    elif fault == "duplicate": data["sources"][1] = s
    elif fault == "order": data["sources"].reverse()
    elif fault == "object": s["object_type"] = "Review"
    elif fault == "tenant": s["tenant"]["org_id"] = "dev-org"
    elif fault == "naive": data["checked_at"] = NOW.replace(tzinfo=None)
    elif fault == "future": s["observed_at"] = NOW + timedelta(seconds=1)
    elif fault == "ref": s["mapping_ref"]["resource_type"] = "Evidence"
    elif fault == "rule": s["quality"]["rule_ref"] = None
    elif fault == "status": s["status"] = "ready"
    elif fault == "counts": s["counts"]["source_active"] = 2
    elif fault == "run_time": s["latest_run"]["finished_at"] = NOW.replace(tzinfo=None)
    elif fault == "run_missing": s["latest_run"] = {"status": "succeeded"}
    with pytest.raises(ValidationError): evaluate(data)


def test_model_copy_does_not_bypass_validation():
    data = InstalledSnapshotReadinessInput.model_validate(payload())
    corrupt = data.model_copy(update={"sources": data.sources[:-1]})
    with pytest.raises(ValidationError):
        SourceReadinessService.evaluate_installed_snapshot(corrupt)


def test_old_entry_marks_exact_expiry_stale():
    from test_source_readiness_service import Facts, _snapshot
    baseline = SourceReadinessService(Facts(_snapshot())).read(org_id="org-org", project_id="dev-project")
    expiry = baseline.sources[0].freshness_expires_at
    current = SourceReadinessService(Facts(_snapshot(checked_at=expiry))).read(org_id="org-org", project_id="dev-project")
    assert current.sources[0].status == "stale"
    assert "SOURCE_DATA_STALE" in current.sources[0].reasons

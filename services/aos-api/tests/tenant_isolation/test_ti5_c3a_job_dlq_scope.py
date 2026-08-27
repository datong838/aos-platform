from __future__ import annotations

from unittest.mock import patch

import pytest

from aos_api.auth import Principal
from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.routers import wave_ext
from aos_api.tenant_scope import TenantScope


SCOPE_A = TenantScope("org-c3-a", "workspace-c3-a")
SCOPE_B = TenantScope("org-c3-b", "workspace-c3-b")


class _FixedUuid:
    hex = "1234567890abcdef1234567890abcdef"


def _principal(scope: TenantScope) -> Principal:
    return Principal(subject="ti5-c3", org_id=scope.org_id, project_id=scope.project_id)


@pytest.fixture(autouse=True)
def _clean_job_dlq_state() -> None:
    with connect() as conn:
        for scope in (SCOPE_A, SCOPE_B):
            conn.execute(
                "INSERT INTO twa_org (id,name) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                (scope.org_id, scope.org_id),
            )
            conn.execute(
                "INSERT INTO twa_workspace (org_id,project_id,name) "
                "VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                (scope.org_id, scope.project_id, scope.project_id),
            )
        conn.commit()
    jobs = dict(wave_ext._jobs)
    dlq = dict(wave_ext._dlq)
    capabilities = dict(wave_ext._capabilities)
    media = dict(wave_ext._media)
    wave_ext._jobs.clear()
    wave_ext._dlq.clear()
    wave_ext._capabilities.clear()
    wave_ext._media.clear()
    yield
    wave_ext._jobs.clear()
    wave_ext._jobs.update(jobs)
    wave_ext._dlq.clear()
    wave_ext._dlq.update(dlq)
    wave_ext._capabilities.clear()
    wave_ext._capabilities.update(capabilities)
    wave_ext._media.clear()
    wave_ext._media.update(media)


def test_capability_job_same_id_is_scoped_and_foreign_status_is_hidden() -> None:
    wave_ext.reg_cap(
        wave_ext.CapRegIn(id="cap-shared", kind="job", endpoint="mock://local"),
        _principal(SCOPE_A),
    )
    with patch("aos_api.routers.wave_ext.uuid.uuid4", return_value=_FixedUuid()):
        job_a = wave_ext.submit_job(
            "cap-shared",
            wave_ext.JobSubmitIn(capabilityId="cap-shared", input={"tenant": "a"}),
            _principal(SCOPE_A),
        )
        job_b = wave_ext.submit_job(
            "cap-shared",
            wave_ext.JobSubmitIn(capabilityId="cap-shared", input={"tenant": "b"}),
            _principal(SCOPE_B),
        )

    assert job_a["jobId"] == job_b["jobId"]
    assert job_a["orgId"] == SCOPE_A.org_id
    assert job_b["orgId"] == SCOPE_B.org_id
    assert wave_ext.job_status(job_a["jobId"], _principal(SCOPE_A))["input"] == {
        "tenant": "a"
    }
    assert wave_ext.job_status(job_b["jobId"], _principal(SCOPE_B))["input"] == {
        "tenant": "b"
    }

    wave_ext._jobs.pop(wave_ext._resource_key(SCOPE_B, job_b["jobId"]))
    with pytest.raises(ApiError) as foreign_error:
        wave_ext.job_status(job_a["jobId"], _principal(SCOPE_B))
    assert foreign_error.value.status_code == 404


def test_dlq_scoped_id_list_retry_and_docintel_failure_are_scoped() -> None:
    with patch("aos_api.routers.wave_ext.uuid.uuid4", return_value=_FixedUuid()):
        item_a = wave_ext.push_dlq({"reason": "a"}, _principal(SCOPE_A))
        item_b = wave_ext.push_dlq({"reason": "b"}, _principal(SCOPE_B))

    assert item_a["id"] != item_b["id"]
    assert wave_ext.list_dlq(_principal(SCOPE_A))["items"] == [item_a]
    assert wave_ext.list_dlq(_principal(SCOPE_B))["items"] == [item_b]
    assert wave_ext.retry_dlq(item_a["id"], _principal(SCOPE_A))["status"] == "retried"
    assert item_b["status"] == "open"

    with pytest.raises(ApiError) as foreign_error:
        wave_ext.retry_dlq(item_a["id"], _principal(SCOPE_B))
    assert foreign_error.value.status_code == 404

    with patch("aos_api.routers.wave_ext.uuid.uuid4", return_value=_FixedUuid()):
        result = wave_ext.docintel_pipeline(
            {"fail": True, "reason": "parse"}, _principal(SCOPE_B)
        )
    docintel_item = wave_ext._dlq[
        wave_ext._resource_key(SCOPE_B, result["dlqId"])
    ]
    assert (docintel_item["orgId"], docintel_item["projectId"]) == SCOPE_B.key


def test_demo_seed_and_purge_handle_scoped_dlq_without_cross_scope_collision() -> None:
    wave_ext.ensure_demo_data_seed(SCOPE_A, force=True)
    wave_ext.ensure_demo_data_seed(SCOPE_B, force=True)
    assert wave_ext._resource_key(SCOPE_A, "dlq-demo-sample") in wave_ext._dlq
    assert wave_ext._resource_key(SCOPE_B, "dlq-demo-sample") in wave_ext._dlq

    from aos_api.data_os_store import purge_demo_surface

    result = purge_demo_surface(wave_ext)
    assert result["removed"]["dlq"] == 2
    assert not wave_ext._dlq

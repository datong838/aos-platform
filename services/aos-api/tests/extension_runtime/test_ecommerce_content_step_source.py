"""No content StepRun may be started from a receipt without its original Run."""

from types import SimpleNamespace

import pytest

from aos_api.ecommerce_content_step_owner import ContentGenerationStepSource, ContentStepConflict
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")


def _source_rows(*, run_id="run-1", status="running", task_id="task-1"):
    return [
        {"invocation_id": "00000000-0000-0000-0000-000000000001",
         "task_ref": {"resourceType": "Task", "resourceId": "task-1"},
         "state": "settled", "provider_receipt_ref": {"resourceId": "provider-1"},
         "usage_receipt_refs": [{"resourceId": "usage-1"}, {"resourceId": "usage-2"}]},
        {"artifact_id": "artifact-7ac1b8d7010bb6cd3a3e", "run_id": run_id,
         "artifact_type": "ecommerce_content", "content_hash": "a" * 64,
         "source": {"invocationId": "00000000-0000-0000-0000-000000000001"}},
        {"task_id": task_id, "status": status, "plan_revision_id": "plan-1",
         "task_status": "executing", "approval_status": "approved",
         "steps": [{"stepKey": "content_generate"}, {"stepKey": "content_review"}]},
    ]


class _Conn:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.queries = []

    def execute(self, query, params=()):
        self.queries.append((str(query), params))
        return SimpleNamespace(fetchone=lambda: next(self.rows))


def test_step_source_requires_settled_independently_verified_original_run():
    journal = SimpleNamespace(read=lambda *_: {"command": {
        "authorityRefs": {"task": {"resourceId": "task-1"}}},
        "result": {"answer": "有来源的内容"}})
    context = lambda *_: {"runId": "run-1"}
    source = ContentGenerationStepSource(
        status_reader=lambda *_: "COMPLETED", journal=journal, context_reader=context)
    conn = _Conn(_source_rows())
    proof = source.read(conn, SCOPE, "reservation-1")
    assert proof.run_id == "run-1"
    assert proof.artifact_id == "artifact-7ac1b8d7010bb6cd3a3e"
    assert proof.task_id == "task-1"
    assert all(params[:2] == SCOPE.key for _, params in conn.queries)

    for changed in (
        _source_rows(run_id="another-run"),
        _source_rows(status="succeeded"),
        _source_rows(task_id="another-task"),
        [*(_source_rows()[:1]),
         {**_source_rows()[1], "source": {"invocationId": "another-invocation"}},
         _source_rows()[2]],
        [*_source_rows()[:2], {**_source_rows()[2], "approval_status": "draft"}],
    ):
        with pytest.raises(ContentStepConflict):
            source.read(_Conn(changed), SCOPE, "reservation-1")
    with pytest.raises(ContentStepConflict, match="COMPLETED"):
        ContentGenerationStepSource(status_reader=lambda *_: "COST_PENDING",
            journal=journal, context_reader=context).read(
            _Conn(_source_rows()), SCOPE, "reservation-1")

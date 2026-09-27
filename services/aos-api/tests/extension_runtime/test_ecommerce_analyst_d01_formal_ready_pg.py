"""Original analysis Task/Plan must reach D01 readiness through canonical Owners."""

import pytest

from aos_api.aip_task_store import AipTaskStore, AipTaskTransitionBlocked
from aos_api.ecommerce_analysis_continuation_context import AnalysisContinuationContext
from aos_api.ecommerce_analysis_continuation_origin import AnalysisContinuationOrigin
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from test_analysis_continuation_context_pg import (
    completed_case, formal_case, preview_case, review_identity, compilation_case,
    publications, context_publication, context_case, startup_case, analysis_case,
    consumer_case, host_case, control_governed, governed, service_case, stored,
    pair, body,
)


pytestmark = [
    pytest.mark.parametrize('startup_case', ['defer-host'], indirect=True),
    pytest.mark.parametrize('stored', ['qualified-runtime'], indirect=True),
]


def test_original_formal_plan_is_schema_only_and_generic_resume_is_denied(completed_case):
    conn, analysis, _claimed, receipt = completed_case
    current = AnalysisContinuationOrigin(AnalysisContinuationContext(analysis)).run_current(
        conn, receipt_ref=receipt, execute=lambda value: value)
    run_id = current['analysisReceipt']['taskRunRef']['resourceId']
    tasks = AipTaskStore(TransactionBoundConnectFactory(
        HostTransaction(conn), analysis.scope))
    timeline = tasks.timeline(analysis.scope, run_id)
    assert timeline.run.status.value == 'paused'
    assert getattr(timeline.plan.approval_status, 'value', timeline.plan.approval_status) == 'approved'
    assert tuple(step.step_key for step in timeline.plan.steps) == (
        'portrait', 'diagnosis', 'solution-design')
    assert all(step.input_refs == [step.input_schema_ref]
               for step in timeline.plan.steps)
    with pytest.raises(AipTaskTransitionBlocked,
                       match='ANALYSIS_BOOTSTRAP_CONTINUATION_AUTHORITY_REQUIRED'):
        tasks.resume_run(
            analysis.scope, run_id,
            expected_run_version=timeline.run.version,
            expected_task_version=timeline.task.version,
            actor=analysis.source.actor,
            idempotency_key='d01-formal-untrusted-resume',
        )
    assert tasks.timeline(analysis.scope, run_id).run.status.value == 'paused'

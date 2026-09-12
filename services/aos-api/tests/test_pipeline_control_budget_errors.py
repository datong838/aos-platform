import pytest

from aos_api.phase5_pipeline_engine import get_engine
from aos_api.pipeline_control_errors import SourceCallBudgetExhausted
from aos_api.tenant_scope import TenantScope


@pytest.mark.parametrize('specific', [True, False])
def test_worker_budget_error_is_bounded_and_does_not_claim_success(specific):
    engine = get_engine()
    engine.reset_all_for_tests()
    scope = TenantScope('dev-org', 'dev-project')
    def fail(**kwargs):
        error = SourceCallBudgetExhausted if specific else RuntimeError
        raise error('source call budget exhausted private business detail')
    engine.register_executor('budget-error-test', fail)
    pipeline = engine.create_pipeline(scope, name='budget', executor_id='budget-error-test', execution_mode='live')
    schedule = engine.create_schedule(scope, name='budget', pipeline_id=pipeline.id)
    try:
        result = engine.run_schedule(scope, schedule.id)
        assert result.status == 'failed'
        assert result.rows_written == 0
        assert result.error_code == ('PIPELINE_SOURCE_CALL_BUDGET_EXHAUSTED' if specific else 'PIPELINE_EXECUTOR_FAILED')
        assert 'private business' not in result.error_message
        if specific:
            assert result.error_message == '本次授权的源调用次数已用完；请查看原运行结果，需要重新读取时先更新审批。'
    finally:
        engine.reset_all_for_tests()

import pytest
from aos_api.phase5_pipeline_engine import get_engine
from aos_api.tenant_scope import TenantScope


@pytest.mark.parametrize('run_id', ['scr-persisted', None])
@pytest.mark.parametrize('durable', [False, True])
def test_dispatch_preserves_supplied_run_identity(run_id,durable):
    engine = get_engine()
    engine.reset_all_for_tests()
    captured = []
    def execute(**kwargs):
        captured.append(kwargs['run_id'])
        assert kwargs.get('durable_ingress',False) is durable
        return {'output_ref': 'dataset://catalog/lineage', 'rows_read': 0, 'rows_written': 0}
    engine.register_executor('lineage-test', execute)
    engine.register_evidence_resolver('dataset', lambda _: True)
    scope = TenantScope('org-org', 'dev-project')
    pipeline = engine.create_pipeline(scope, name='lineage', executor_id='lineage-test', execution_mode='live')
    try:
        engine.execute_pipeline_once(scope, pipeline.id, run_id=run_id,durable_ingress=durable)
        assert len(captured) == 1
        assert captured[0] == run_id if run_id else captured[0].startswith('pipeline-run-')
    finally:
        engine.reset_all_for_tests()

"""Invalid canonical output must not create a successful Dataset first."""
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from aos_api import ec_live_executor as executor
from aos_api.tenant_scope import TenantScope


@pytest.mark.parametrize('rows', [[{}], [{'ot': 'Product'}]])
def test_invalid_output_rejected_before_either_sink(rows):
    with ExitStack() as stack:
        for name in ('ensure_store_assembled', '_stamp_snapshot_observation',
                     '_enrich_payment_order_create_time', '_enrich_shipment_order_pay_time',
                     '_make_link_aggregator', 'handle_failure'):
            stack.enter_context(patch.object(executor, name))
        stack.enter_context(patch.object(executor, 'fetch_source_rows', return_value=[]))
        for name in ('normalize_rows', 'apply_derived_metrics', 'build_link_rows'):
            stack.enter_context(patch.object(executor, name, return_value=rows))
        dataset = stack.enter_context(patch.object(executor, 'sink_to_dataset'))
        ot = stack.enter_context(patch.object(executor, 'sink_to_ot'))
        stack.enter_context(patch('aos_api.ecom_projector.project_until_caught_up'))
        with pytest.raises((ValueError, KeyError)):
            executor.ec_live_executor(pipeline=SimpleNamespace(id='p02-test'), nodes=[],
                node_id=None, sample_input=None, execution_kind='live', cancel_event=None,
                deadline=0, scope=TenantScope('org-org', 'dev-project'), run_id='preflight-test')
        dataset.assert_not_called()
        ot.assert_not_called()


@pytest.mark.parametrize('failure', ['ot', 'derived', 'projection', None])
def test_dataset_published_only_after_authoritative_stages(failure):
    events = []
    def stage(name, result=None):
        def run(*args, **kwargs):
            events.append(name)
            if failure == name:
                raise RuntimeError('STAGE_FAILED')
            return result
        return run
    with ExitStack() as stack:
        for name in ('ensure_store_assembled', '_stamp_snapshot_observation',
                     '_enrich_payment_order_create_time', '_enrich_shipment_order_pay_time',
                     '_make_link_aggregator', 'handle_failure'):
            stack.enter_context(patch.object(executor, name))
        for name in ('fetch_source_rows', 'normalize_rows', 'apply_derived_metrics', 'build_link_rows'):
            stack.enter_context(patch.object(executor, name, return_value=[]))
        stack.enter_context(patch.object(executor, 'sink_to_ot', side_effect=stage('ot')))
        stack.enter_context(patch.object(executor, 'sink_derived_metrics', side_effect=stage('derived', {})))
        stack.enter_context(patch('aos_api.ecom_projector.project_until_caught_up', side_effect=stage('projection', {})))
        stack.enter_context(patch.object(executor, 'sink_to_dataset', side_effect=stage('dataset', SimpleNamespace(id='saved'))))
        def execute():
            return executor.ec_live_executor(pipeline=SimpleNamespace(id='p02-test'), nodes=[],
                node_id=None, sample_input=None, execution_kind='live', cancel_event=None,
                deadline=0, scope=TenantScope('org-org', 'dev-project'), run_id='order-test')
        if failure:
            with pytest.raises(RuntimeError, match='STAGE_FAILED'):
                execute()
            assert 'dataset' not in events
        else:
            assert execute()['output_ref'] == 'dataset://catalog/saved'
            assert events == ['ot', 'derived', 'projection', 'dataset']

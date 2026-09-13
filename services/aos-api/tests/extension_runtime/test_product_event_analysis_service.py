"""Three-phase flow only; explicit authority and Host-write test doubles."""
import asyncio
from contextlib import contextmanager
from types import SimpleNamespace
import pytest


@pytest.mark.parametrize('fault',[None,'drift','compute','write'])
def test_analysis_prepare_compute_commit_without_transaction_across_await(fault):
    from aos_api.ecommerce_product_event_analysis_service import ProductEventAnalysisService
    events=[];active=[];phases=[]
    @contextmanager
    def connect(scope):
        assert not active
        active.append(True);events.append('open')
        try:yield SimpleNamespace(commit=lambda:events.append('commit'))
        finally:active.clear();events.append('close')
    service=object.__new__(ProductEventAnalysisService)
    service.scope=object();service.connect=connect
    def phase(conn,claimed,callback):
        phases.append(True)
        snapshot={'revision':2 if fault=='drift' and len(phases)==2 else 1}
        return callback(snapshot,{'request':'exact'},'dispatch')
    service._phase=phase
    async def build(request):
        assert not active
        events.append('compute')
        if fault=='compute':raise TimeoutError()
        return {'command':'exact'}
    service.port=SimpleNamespace(build_start=build)
    def write(conn,claimed,dispatch,command):
        assert active
        events.append('write')
        if fault=='write':raise ValueError('rollback')
        return {'resourceId':'receipt'}
    service._write=write
    if fault:
        with pytest.raises((ValueError,TimeoutError)):
            asyncio.run(service.handle(object()))
        assert 'commit' not in events
        if fault=='drift':assert 'write' not in events
    else:
        assert asyncio.run(service.handle(object()))=={'resourceId':'receipt'}
        assert events==['open','close','compute','open','write','commit','close']
    assert events.count('compute')==1


def test_write_uses_sealed_host_and_rechecks_claim(monkeypatch):
    from aos_api import ecommerce_product_event_analysis_service as module
    from aos_api.tenant_scope import TenantScope
    service=object.__new__(module.ProductEventAnalysisService)
    service.scope=TenantScope('org-org','dev-project')
    events=[];registry=object();connection=object();claim=object();dispatch=object();command={}
    monkeypatch.setattr(module,'build_runtime_ecommerce_growth_registry',lambda:registry)
    def ports(value,*,connect_factory):
        assert value is registry
        assert type(connect_factory) is module.TransactionBoundConnectFactory
        def commit(**kwargs):
            assert kwargs==dict(dispatch_ref=dispatch,command=command)
            events.append('host-commit-within-outer-transaction')
            return {'receiptRef':{'resourceId':'exact'}}
        return SimpleNamespace(runtime_port=SimpleNamespace(commit=commit))
    monkeypatch.setattr(module,'build_ecommerce_growth_host_ports',ports)
    monkeypatch.setattr(module.AutomationOccurrenceStore,'_lock_claim',lambda *args:events.append('recheck-claim'))
    assert service._write(connection,claim,dispatch,command)=={'resourceId':'exact'}
    assert events==['host-commit-within-outer-transaction','recheck-claim']

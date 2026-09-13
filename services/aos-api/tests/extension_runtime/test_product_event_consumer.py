"""Three-phase ordering doubles; does not prove current source authorization."""
import asyncio
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace
import pytest
from aos_api.ecommerce_product_event_consumer import ProductEventConsumptionService
from aos_api.ecommerce_product_event_window_port import InstalledProductEventWindowPort
from aos_api.extension_runtime.installed_package_invoker import CurrentInstalledPackageInvoker
from aos_api.tenant_scope import TenantScope
from test_product_event_window_port import payload, response


def fixture_service(monkeypatch,*,drift=False,empty=False,error=None):
    events=[];active=[];phase_count=[]
    service=object.__new__(ProductEventConsumptionService)
    service.scope=TenantScope('org-org','dev-project');service.actor='fixture'
    @contextmanager
    def connect(scope):
        active.append(True)
        try:yield SimpleNamespace(commit=lambda:events.append('commit'))
        finally:active.pop()
    service.connect=connect
    def phase(conn,policy_id,consume):
        phase_count.append(1)
        snapshot={'revision':2 if drift and len(phase_count)>1 else 1}
        request=None if empty else payload()
        events.append('read')
        return consume(snapshot,request,object())
    service._phase=phase
    invoker=object.__new__(CurrentInstalledPackageInvoker);invoker.package_id='domain.ecommerce.core'
    async def invoke(self,operation,request):
        assert not active
        events.append('compute')
        if error:raise error
        return response(request)
    monkeypatch.setattr(CurrentInstalledPackageInvoker,'__call__',invoke)
    service.port=InstalledProductEventWindowPort(invoker)
    def write(*args,**kwargs):events.append('write');return ('receipt',)
    monkeypatch.setattr(service,'_write',write)
    return service,events


def test_three_phases_do_not_hold_transaction_during_ipc(monkeypatch):
    service,events=fixture_service(monkeypatch)
    assert asyncio.run(service.consume('policy'))==('receipt',)
    assert events==['read','compute','read','write','commit']


def test_changed_current_snapshot_does_not_write(monkeypatch):
    service,events=fixture_service(monkeypatch,drift=True)
    with pytest.raises(ValueError,match='snapshot'):asyncio.run(service.consume('policy'))
    assert events==['read','compute','read']


def test_empty_current_batch_never_invokes_or_writes(monkeypatch):
    service,events=fixture_service(monkeypatch,empty=True)
    assert asyncio.run(service.consume('policy'))==()
    assert events==['read']


def test_unknown_calculation_does_not_retry_or_write(monkeypatch):
    service,events=fixture_service(monkeypatch,error=TimeoutError('unknown'))
    with pytest.raises(TimeoutError):asyncio.run(service.consume('policy'))
    assert events==['read','compute']

import asyncio
from copy import deepcopy
import pytest
from aos_api.extension_runtime.installed_package_invoker import CurrentInstalledPackageInvoker
from aos_api.ecommerce_product_event_window_port import InstalledProductEventWindowPort
from aos_api.asset_registry.canonical_json import canonical_sha256


def payload():
    return dict(schemaVersion='aos.product-event-window-request/v1',effectiveFrom='2026-09-14T00:00:00+00:00',
        effectiveUntil='2026-09-14T01:00:00+00:00',maxSourceAgeSeconds=3600,recoveryWindowSeconds=600,
        events=[dict(eventKey='a'*64,sourceUpdatedAt='2026-09-14T00:00:00+00:00',recordedAt='2026-09-14T00:00:00+00:00')])


def response(p):
    return dict(schemaVersion='aos.product-event-window-result/v1',requestHash=canonical_sha256(p),
        events=[dict(eventKey='a'*64,deadline='2026-09-14T00:10:00+00:00')])


def port(monkeypatch,run):
    invoker=object.__new__(CurrentInstalledPackageInvoker);invoker.package_id='domain.ecommerce.core'
    monkeypatch.setattr(CurrentInstalledPackageInvoker,'__call__',run)
    return InstalledProductEventWindowPort(invoker)


def test_once_and_input_isolation(monkeypatch):
    calls=[];p=payload();before=deepcopy(p)
    async def run(self,op,body):
        calls.append(op);result=response(body);body['events'].clear();return result
    result=asyncio.run(port(monkeypatch,run).calculate(p))
    assert calls==['ecommerce_core_product_event_windows'] and p==before
    assert result==response(p)


def test_timeout_never_retried(monkeypatch):
    calls=[]
    async def run(*args):calls.append(1);raise TimeoutError('unknown')
    with pytest.raises(TimeoutError):asyncio.run(port(monkeypatch,run).calculate(payload()))
    assert calls==[1]


@pytest.mark.parametrize('change',['hash','key','extend','naive','fraction','extra','count'])
def test_invalid_result_rejected(monkeypatch,change):
    async def run(self,op,p):
        r=response(p)
        if change=='hash':r['requestHash']='sha256:'+'0'*64
        if change=='key':r['events'][0]['eventKey']='b'*64
        if change=='extend':r['events'][0]['deadline']='2026-09-14T00:10:01+00:00'
        if change=='naive':r['events'][0]['deadline']='2026-09-14T00:10:00'
        if change=='fraction':r['events'][0]['deadline']='2026-09-14T00:09:59.1+00:00'
        if change=='extra':r['approved']=True
        if change=='count':r['events']=[]
        return r
    with pytest.raises(ValueError):asyncio.run(port(monkeypatch,run).calculate(payload()))


def test_bad_request_does_not_invoke(monkeypatch):
    async def run(*args):pytest.fail('invalid request invoked')
    p=payload();p['maxSourceAgeSeconds']=True
    with pytest.raises(ValueError):asyncio.run(port(monkeypatch,run).calculate(p))


def test_arbitrary_callback_or_other_package_cannot_construct_port():
    with pytest.raises(TypeError):InstalledProductEventWindowPort(lambda:None)
    invoker=object.__new__(CurrentInstalledPackageInvoker);invoker.package_id='solution.ecommerce.growth'
    with pytest.raises(ValueError):InstalledProductEventWindowPort(invoker)

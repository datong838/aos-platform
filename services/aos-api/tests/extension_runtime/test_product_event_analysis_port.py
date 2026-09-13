import asyncio
from copy import deepcopy
import pytest
from aos_api.asset_registry.canonical_json import canonical_sha256


def request():
    def ref(kind):
        return dict(resourceType=kind,resourceId='id',revision=1,contentHash='sha256:'+'a'*64)
    return dict(kind='build_analysis_start',occurrenceRef=ref('AutomationOccurrence'),
                caseRef=ref('BusinessInvestigationCaseRevision'),profileRef=ref('InvestigationProfileRevision'),
                cutoffAt='2026-09-14T00:00:00+00:00',idempotencyKey='original')


def command(payload):
    value={key:deepcopy(v) for key,v in payload.items() if key!='kind'}
    value.update(operation='runtime.analysis.start',priorReceiptRef=None,requirementRef=None,fulfillmentRef=None,checkpointRef=None)
    return {**value,'requestHash':canonical_sha256(value)}


@pytest.mark.parametrize('fault',[None,'case','key','time','hash','extra','timeout','package'])
def test_installed_analysis_command_binding(monkeypatch,fault):
    from aos_api import ecommerce_product_event_analysis_port as module
    calls=[]
    class Invoker:
        package_id='solution.ecommerce.growth'
        async def __call__(self,operation,payload):
            calls.append(operation)
            if fault=='timeout':raise TimeoutError()
            result=command(payload)
            if fault=='case':result['caseRef']['resourceId']='other'
            if fault=='key':result['idempotencyKey']='other'
            if fault=='time':result['cutoffAt']='2026-09-14T01:00:00+00:00'
            if fault=='extra':result['approved']=True
            if fault in {'case','key','time','extra'}:
                result['requestHash']=canonical_sha256({k:v for k,v in result.items() if k!='requestHash'})
            if fault=='hash':result['requestHash']='sha256:'+'b'*64
            if fault=='package':self.package_id='domain.ecommerce.core'
            payload['caseRef']['resourceId']='mutated-input'
            return result
    monkeypatch.setattr(module,'CurrentInstalledPackageInvoker',Invoker)
    payload=request();original=deepcopy(payload)
    port=module.InstalledProductEventAnalysisPort(Invoker())
    if fault:
        with pytest.raises((ValueError,TimeoutError)):
            asyncio.run(port.build_start(payload))
    else:
        assert asyncio.run(port.build_start(payload))==command(original)
    assert payload==original
    assert calls==['ecommerce_growth_analysis_advance']


@pytest.mark.parametrize('fault',['extra','key','cutoff','ref','wrong-package','wrong-invoker'])
def test_invalid_analysis_request_never_invokes(monkeypatch,fault):
    from aos_api import ecommerce_product_event_analysis_port as module
    calls=[]
    class Invoker:
        package_id='solution.ecommerce.growth'
        async def __call__(self,*args):calls.append(args)
    monkeypatch.setattr(module,'CurrentInstalledPackageInvoker',Invoker)
    invoker=Invoker();payload=request()
    if fault=='extra':payload['approved']=True
    elif fault=='key':payload['idempotencyKey']=' '
    elif fault=='cutoff':payload['cutoffAt']='2026-09-14T00:00:00'
    elif fault=='ref':payload['caseRef']['revision']=True
    elif fault=='wrong-package':invoker.package_id='domain.ecommerce.core'
    else:invoker=object()
    with pytest.raises((ValueError,TypeError)):
        asyncio.run(module.InstalledProductEventAnalysisPort(invoker).build_start(payload))
    assert calls==[]

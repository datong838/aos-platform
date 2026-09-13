import asyncio
from copy import deepcopy
import pytest
from test_ecommerce_analysis_start_operation import _package
from aos_api.ecommerce_business_investigation_profile_catalog import INITIAL_STORE_PROFILE
from aos_api.asset_registry.canonical_json import canonical_sha256


@pytest.mark.parametrize('fault',[None,'profile','compiler','source','order','skill','extra','hash','package','timeout'])
def test_blueprint_port_revalidates_installed_response(monkeypatch,fault):
    from aos_api import ecommerce_product_event_analysis_port as module
    calls=[]
    class Invoker:
        package_id='solution.ecommerce.growth'
        async def __call__(self,operation,payload):
            calls.append((operation,deepcopy(payload)))
            if fault=='timeout':raise TimeoutError()
            result=_package().handle(operation,payload,object())
            if fault=='profile':result['profileRef']['revision']=2
            elif fault=='compiler':result['compilerProfile']='other'
            elif fault=='source':result['stageTemplateRequest']['sourceBundleRef']['contentHash']='f'*64
            elif fault=='order':result['stageSkills'].reverse()
            elif fault=='skill':result['stageSkills'][0]['skillId']=' '
            elif fault=='extra':result['approved']=True
            result['contentHash']=canonical_sha256({k:v for k,v in result.items() if k!='contentHash'})
            if fault=='hash':result['contentHash']='sha256:'+'f'*64
            if fault=='package':self.package_id='other'
            return result
    monkeypatch.setattr(module,'CurrentInstalledPackageInvoker',Invoker)
    port=module.InstalledProductEventAnalysisPort(Invoker())
    def run():return asyncio.run(port.build_compilation_blueprint(INITIAL_STORE_PROFILE))
    if fault:
        with pytest.raises((ValueError,TimeoutError)):run()
    else:
        assert run()['compilerProfile']==INITIAL_STORE_PROFILE.responsibility_template_code
    assert len(calls)==1

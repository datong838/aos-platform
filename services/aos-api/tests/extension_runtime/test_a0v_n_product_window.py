import importlib

import pytest


def test_n_window_uses_exact_policy10_and_route_revision():
    window=importlib.import_module('a0v_n_product_window')
    natural=importlib.import_module('a0v_n_natural_product_event')
    assert window.authority_profile().previous_reference('selection') is None
    assert window.authority_profile().previous_reference('control') is None
    assert window.authority_profile().previous_reference('binding')['revision']==15
    assert window.policy_profile().previous_policy_payload()['revision']==9
    assert natural.POLICY_REVISION==10
    assert natural.EXPECTED_BINDING_REVISION==1
    assert natural.EXPECTED_GROUP_REVISION==43
    assert natural.INITIAL_TIMEOUT_SECONDS==3300


def test_n_natural_window_rejects_route_and_tenant_drift():
    module=importlib.import_module('a0v_n_natural_product_event')
    from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
    from datetime import datetime,timezone,timedelta
    operations=sorted(set(ECOMMERCE_GROWTH_OPERATIONS)|{'ecommerce_growth_event_control'})
    value={'schedule':{'cron':'0 * * * *','pipeline_id':'P02-product-qyh',
             'ingest':{'kind':'pipeline-live-v1','pipelineId':'P02-product-qyh'}},
      'policy':{'current_revision':10,'enabled':False},
      'binding':{'policy_revision':10,'installation_id':module.current.N_ID,
        'generation':module.current.N_GENERATION,'execution_epoch':3,'approved':True,
        'enabled':True,'revision':1,'effective_until':datetime.now(timezone.utc)+timedelta(minutes=30)},
      'routes':[{'operation_id':operation,'handler_kind':'extension',
        'installation_id':module.current.N_ID,'generation':module.current.N_GENERATION,
        'execution_epoch':3,'operation_fence':False,'cutover_group_revision':43}
        for operation in operations],
      'expectedOperations':operations,'inflight':{'running':0,'unresolved':0},
      'negativeCanaryDispatch':0}
    assert module.validate_ready(value)['policy']['current_revision']==10
    value['routes'][0]['cutover_group_revision']=42
    with pytest.raises(ValueError,match='exact N'):
        module.validate_ready(value)


def test_n_recovery_requires_one_existing_successful_cron_ingress(monkeypatch):
    module=importlib.import_module('a0v_n_natural_product_event')
    monkeypatch.setattr(module,'validate_ready',lambda value:value)
    value={'schedule':{'enabled':False},
      'runs':[{'id':'scr-one','status':'succeeded','trigger':'cron'}],
      'ingress':[{'run_id':'scr-one'}],'occurrences':[],'attempts':[],
      'investigationRuns':[]}
    assert module._validate_recovery(value) is value
    value['runs'][0]['trigger']='manual'
    with pytest.raises(ValueError,match='exact failed'):
        module._validate_recovery(value)

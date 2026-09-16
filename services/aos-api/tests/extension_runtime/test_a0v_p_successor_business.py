import importlib
import json

import pytest


def _snapshot(module):
    return {'head':{'installation_id':module.P_ID,'etag_version':5,'state':'active',
             'lock_hash':module.LOCK,'overlay_revision':'a0v-canonical-ecommerce-v1'},
        'bindings':[{'generation':module.P_GENERATION,'revision':4,'execution_epoch':3,
             'enabled':True,'operation_fence':False,'desired_state':'enabled',
             'observed_state':'ready','config_ref':module.CONFIG}],
        'resources':[{'cleanup_state':'pending','observed_release':False} for _ in range(3)],
        'operations':[{'kind':kind,'status':'succeeded'} for kind in
            ('runtime-apply','runtime-verify','configure','enable')],
        'canaryInstallations':0}


def test_p_successor_requires_exact_n_detach_and_group(monkeypatch):
    module=importlib.import_module('a0v_p_successor_business')
    from aos_api.asset_registry.canonical_json import canonical_sha256
    from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
    authority={'exact':'n-detach'};digest=canonical_sha256(authority)
    monkeypatch.setattr(module,'DETACH_HASH',digest)
    parent={'receipt_id':module.DETACH,'phase':'detach','org_id':'org-org',
      'project_id':'dev-project','authority_data':authority,'content_hash':digest}
    routes=[{'operation_id':operation,'handler_kind':'legacy','installation_id':None,
      'generation':None,'execution_epoch':None,'operation_fence':True,
      'revision':26,'cutover_group_revision':47}
      for operation in sorted(ECOMMERCE_GROWTH_OPERATIONS)]
    request=module.request_from(_snapshot(module),parent,routes,
      {'installation_id':module.N_ID,'state':'uninstalled','etag_version':6})
    assert request.expectedGroupRevision==47
    routes[0]['operation_fence']=False
    with pytest.raises(ValueError,match='detached N route group'):
        module.request_from(_snapshot(module),parent,routes,
          {'installation_id':module.N_ID,'state':'uninstalled','etag_version':6})


def test_p_cutover_target_uses_registration_receipt():
    successor=importlib.import_module('a0v_p_successor_business')
    cutover=importlib.import_module('a0v_p_successor_cutover')
    from aos_api.ecommerce_growth_successor_registration import SuccessorDispatchRegistrationRequest
    request=SuccessorDispatchRegistrationRequest.model_validate({
      'schemaVersion':'aos.ecommerce.successor-dispatch-registration/v1',
      'expectedGroupRevision':47,
      'predecessorDetachReceiptRef':{'resourceType':'DispatchDisableDetachReceipt',
        'resourceId':successor.DETACH,'revision':1,'contentHash':successor.DETACH_HASH},
      'registration':{'schemaVersion':'aos.ecommerce.first-dispatch-registration/v1',
        'installationRef':{'installationId':successor.P_ID,'revision':5,
          'lockHash':successor.LOCK,'overlayRevision':'a0v-canonical-ecommerce-v1'},
        'generation':successor.P_GENERATION,'bindingRevision':4,'executionEpoch':3,
        'configRef':successor.CONFIG,'groupId':successor.GROUP,'idempotencyKey':successor.KEY}})
    registration={'outcome':'CURRENT_P_SUCCESSOR_REGISTERED',
      'request':request.model_dump(mode='json',by_alias=True),
      'receipt':{'receiptId':'receipt','contentHash':'sha256:'+'1'*64,
        'requestHash':request.request_hash()}}
    target,policy=cutover.target(registration)
    assert target['expectedGroupRevision']==47
    assert target['targetInstallationId']==successor.P_ID
    assert policy['externalEffectsAllowed'] is False


def test_p_cutover_existing_intent_never_resends(monkeypatch,tmp_path):
    cutover=importlib.import_module('a0v_p_successor_cutover')
    monkeypatch.setattr(cutover,'STATE',tmp_path)
    (tmp_path/'prepare-intent.json').write_text(json.dumps({'retained':True}))
    class Plane:
        ecommerce_growth_cutover_service=object()
    with pytest.raises(ValueError,match='never resend'):
        cutover.invoke('prepare',Plane())

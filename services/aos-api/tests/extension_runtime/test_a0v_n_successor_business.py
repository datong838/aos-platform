import importlib
import json
from pathlib import Path

import pytest


def _snapshot(module):
    return {'head':{'installation_id':module.N_ID,'etag_version':5,'state':'active',
             'lock_hash':module.LOCK,'overlay_revision':'a0v-canonical-ecommerce-v1'},
        'bindings':[{'generation':module.N_GENERATION,'revision':4,'execution_epoch':3,
             'enabled':True,'operation_fence':False,'desired_state':'enabled',
             'observed_state':'ready','config_ref':module.CONFIG}],
        'resources':[{'cleanup_state':'pending','observed_release':False} for _ in range(3)],
        'operations':[{'kind':kind,'status':'succeeded'} for kind in
            ('runtime-apply','runtime-verify','configure','enable')],
        'canaryInstallations':0}


def test_n_successor_identity_is_fixed():
    module=importlib.import_module('a0v_n_successor_business')
    assert module.N_ID=='d42cd39a-bc44-403b-a184-c241cae7769e'
    assert module.N_GENERATION=='677046ff-6147-4b3b-905d-9e12964b6581'
    assert module.DETACH=='e43b1b5c-77b7-4fc2-bb35-3cb29a9a54c2'


def test_n_successor_requires_exact_detached_group(monkeypatch):
    module=importlib.import_module('a0v_n_successor_business')
    from aos_api.asset_registry.canonical_json import canonical_sha256
    from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
    authority={'exact':'parent'}
    monkeypatch.setattr(module,'DETACH_HASH',canonical_sha256(authority))
    parent={'receipt_id':module.DETACH,'phase':'detach','org_id':'org-org',
            'project_id':'dev-project','authority_data':authority,
            'content_hash':canonical_sha256(authority)}
    routes=[{'operation_id':operation,'handler_kind':'legacy','installation_id':None,
             'generation':None,'execution_epoch':None,'operation_fence':True,
             'revision':23,'cutover_group_revision':41}
            for operation in sorted(ECOMMERCE_GROWTH_OPERATIONS)]
    request=module.request_from(_snapshot(module),parent,routes,
        {'installation_id':module.L_ID,'state':'uninstalled','etag_version':6})
    assert request.expectedGroupRevision==41
    routes[0]['operation_fence']=False
    with pytest.raises(ValueError,match='detached L route group'):
        module.request_from(_snapshot(module),parent,routes,
            {'installation_id':module.L_ID,'state':'uninstalled','etag_version':6})


def test_n_cutover_target_uses_immutable_registration_receipt():
    successor=importlib.import_module('a0v_n_successor_business')
    cutover=importlib.import_module('a0v_n_successor_cutover')
    from aos_api.ecommerce_growth_successor_registration import SuccessorDispatchRegistrationRequest
    request=SuccessorDispatchRegistrationRequest.model_validate({
        'schemaVersion':'aos.ecommerce.successor-dispatch-registration/v1',
        'expectedGroupRevision':41,
        'predecessorDetachReceiptRef':{'resourceType':'DispatchDisableDetachReceipt',
            'resourceId':successor.DETACH,'revision':1,'contentHash':successor.DETACH_HASH},
        'registration':{'schemaVersion':'aos.ecommerce.first-dispatch-registration/v1',
            'installationRef':{'installationId':successor.N_ID,'revision':5,
                'lockHash':successor.LOCK,'overlayRevision':'a0v-canonical-ecommerce-v1'},
            'generation':successor.N_GENERATION,'bindingRevision':4,'executionEpoch':3,
            'configRef':successor.CONFIG,'groupId':successor.GROUP,
            'idempotencyKey':successor.KEY}})
    registration={'outcome':'CURRENT_N_SUCCESSOR_REGISTERED',
        'request':request.model_dump(mode='json',by_alias=True),
        'receipt':{'receiptId':'receipt','contentHash':'sha256:'+'1'*64,
                   'requestHash':request.request_hash()}}
    target,policy=cutover.target(registration)
    assert target['expectedGroupRevision']==41
    assert target['targetRuntimeRevision']==4
    assert target['registrationReceiptRef']['resourceId']=='receipt'
    assert policy['externalEffectsAllowed'] is False


def test_n_cutover_existing_intent_never_resends(monkeypatch,tmp_path):
    cutover=importlib.import_module('a0v_n_successor_cutover')
    monkeypatch.setattr(cutover,'STATE',tmp_path)
    (tmp_path/'prepare-intent.json').write_text(json.dumps({'retained':True}))
    class Plane:
        ecommerce_growth_cutover_service=object()
    with pytest.raises(ValueError,match='never resend'):
        cutover.invoke('prepare',Plane())


def test_n_final_verifier_rejects_route_or_host_drift():
    verifier=importlib.import_module('a0v_n_successor_cutover_verify')
    path=Path(__file__).resolve().parents[4]/'.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/sc4-5l6y5f4-w-final-state.json'
    value=json.loads(path.read_text())
    assert verifier.validate(value)['outcome']=='N_SUCCESSOR_NINE_ROUTE_CUTOVER_GREEN'
    changed=json.loads(path.read_text());changed['database']['routes'][0]['operation_fence']=True
    with pytest.raises(ValueError,match='database state'):
        verifier.validate(changed)
    changed=json.loads(path.read_text());changed['runtimeHost']['liveTargets'][0]['installationId']='wrong'
    with pytest.raises(ValueError,match='Runtime Host target'):
        verifier.validate(changed)

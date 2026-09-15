"""Fixed G successor registration using real signed service authority."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT.parent/'.aos-recovery-20260916/state/event-complete-package/business/successor-g'
G_ID='4b081ad7-2cf6-4188-bc18-870726da1262'
G_GENERATION='1c8d9a2d-0a1b-4caa-9fef-528568fd2629'
LOCK='sha256:3997ccbf5729e46dd7947db59d3093b9963e5e74c5bdfa627003c8fbacfad1cc'
CONFIG={'configurationId':'bf6875bf-c01b-46ad-bb1f-d7c634369f5e','revision':1,'hash':'sha256:e420c697c1969955a8d44ed3b7e2c0497416c72436433fdc9fcd982bd942e796'}
DETACH='3a0aa78f-c6c7-4584-9792-b6491e16f67d'
GROUP='6a402d31-83ad-546c-807f-508c87498ce1'
KEY='a0v-qyh-event-complete-generation-g-successor-v1'
ACTOR='a0v-ecommerce-growth-1.4-runtime-owner'


def request_from(snapshot, parent):
    from aos_api.ecommerce_growth_successor_registration import SuccessorDispatchRegistrationRequest
    from aos_api.asset_registry.canonical_json import canonical_sha256
    head=snapshot['head'];bindings=snapshot['bindings']
    if (str(head['installation_id'])!=G_ID or head['etag_version']!=5 or head['state']!='active'
        or head['lock_hash']!=LOCK or head['overlay_revision']!='a0v-canonical-ecommerce-v1'
        or len(bindings)!=1 or snapshot['canaryInstallations']!=0):raise ValueError('exact G installation required')
    b=bindings[0]
    if (str(b['generation'])!=G_GENERATION or b['revision']!=4 or b['execution_epoch']!=3
        or b['enabled'] is not True or b['operation_fence'] is not False
        or b['desired_state']!='enabled' or b['observed_state']!='ready' or b['config_ref']!=CONFIG):
        raise ValueError('exact ready G binding required')
    if (str(parent['receipt_id'])!=DETACH or parent['phase']!='detach'
        or parent['org_id']!='org-org' or parent['project_id']!='dev-project'
        or canonical_sha256(parent['authority_data'])!=parent['content_hash']):raise ValueError('exact parent detach required')
    return SuccessorDispatchRegistrationRequest.model_validate(dict(
        schemaVersion='aos.ecommerce.successor-dispatch-registration/v1',expectedGroupRevision=10,
        predecessorDetachReceiptRef=dict(resourceType='DispatchDisableDetachReceipt',resourceId=DETACH,revision=1,contentHash=parent['content_hash']),
        registration=dict(schemaVersion='aos.ecommerce.first-dispatch-registration/v1',
            installationRef=dict(installationId=G_ID,revision=5,lockHash=LOCK,overlayRevision=head['overlay_revision']),
            generation=G_GENERATION,bindingRevision=4,executionEpoch=3,configRef=CONFIG,groupId=GROUP,idempotencyKey=KEY)))


def setup():
    sys.dont_write_bytecode=True
    sys.path.insert(0,str(ROOT/'services/aos-api'))
    from a0v_event_complete_product_api import load_launcher
    if load_launcher().preflight()['outcome']!='CONTROLLED_API_LOCAL_DIAGNOSTIC_PREFLIGHT_GREEN':
        raise ValueError('controlled identity preflight required')
    import os
    os.environ['AOS_EXTENSION_RUNTIME_HOST_ENABLED']='0'
    from aos_api.asset_registry.control_wiring import build_runtime_control_plane
    from aos_api.ecommerce_growth_registration_connection import registration_connection
    return build_runtime_control_plane(registration_connect=registration_connection)


def current_request():
    from a0v_ecommerce_event_complete_reinstall import load_profile
    from a0v_formal_text_model_renewal import database_connect
    profile=load_profile();snapshot=profile.observe_installation(G_ID)
    with database_connect('aos_meta_head')() as conn:
        parent=conn.execute('''SELECT org_id,project_id,receipt_id,phase,authority_data,content_hash
            FROM extension_dispatch_lifecycle_receipt WHERE org_id='org-org' AND project_id='dev-project'
            AND receipt_id=%s''',(DETACH,)).fetchone()
    if parent is None:raise ValueError('retained detach missing')
    return request_from(snapshot,dict(parent))


def register(plane, request):
    from aos_api.tenant_scope import TenantScope
    from a0v_qyh_current_product_event_first_chain import freeze,freeze_or_match
    service=plane.first_dispatch_registration_service;scope=TenantScope('org-org','dev-project')
    intent=STATE/'register-intent.json';material=request.model_dump(mode='json',by_alias=True)
    existed=intent.exists();freeze_or_match(intent,material)
    if existed:
        receipt=service.read_successor_receipt(scope=scope,installation_id=G_ID,idempotency_key=KEY,actor=ACTOR)
        replayed=True
    else:
        receipt=service.register_successor(scope=scope,request=request,actor=ACTOR)
        replayed=receipt['replayed']
    if not receipt or receipt['requestHash']!=request.request_hash():raise ValueError('exact registered request readback required')
    result=dict(outcome='CURRENT_G_SUCCESSOR_REGISTERED',request=material,receipt=receipt,replayed=replayed)
    path=STATE/'register-result.json'
    if not path.exists():freeze(path,result)
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['preview','register']);args=parser.parse_args()
    plane=setup();request=current_request()
    result=(dict(outcome='CURRENT_F_SUCCESSOR_REQUEST_PREVIEW',request=request.model_dump(mode='json',by_alias=True),requestHash=request.request_hash())
            if args.mode=='preview' else register(plane,request))
    print(json.dumps(result,ensure_ascii=False,indent=2,default=str))


if __name__=='__main__':main()

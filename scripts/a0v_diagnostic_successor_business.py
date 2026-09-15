"""Fixed H successor registration using real signed service authority."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT.parent/'.aos-recovery-20260916/state/host-diagnostic-recovery/business/successor-h/registration-v2'
G_ID='1cc13337-c1de-40a7-b45e-acb41f20a19b'
G_GENERATION='ba5d7266-5e7e-454f-85c0-04709305592f'
LOCK='sha256:b993a02c792ddd0dac0345243631f8a49aac0b6075e3b3ac71b1c504bb9e7bce'
CONFIG={'configurationId':'e83b25ec-4c20-46b7-a686-b1bcec973b9f','revision':1,'hash':'sha256:316dffe386f4982d065bd3bb5956ec3dffcc856d1494349c8222cd3ca281b1ba'}
DETACH='4cfd53a7-af4a-48ce-97e6-da45d86caf44'
GROUP='6a402d31-83ad-546c-807f-508c87498ce1'
KEY='a0v-qyh-event-complete-generation-h-successor-v2'
ACTOR='a0v-ecommerce-growth-1.4-runtime-owner'


def request_from(snapshot, parent):
    from aos_api.ecommerce_growth_successor_registration import SuccessorDispatchRegistrationRequest
    from aos_api.asset_registry.canonical_json import canonical_sha256
    head=snapshot['head'];bindings=snapshot['bindings']
    if (str(head['installation_id'])!=G_ID or head['etag_version']!=5 or head['state']!='active'
        or head['lock_hash']!=LOCK or head['overlay_revision']!='a0v-canonical-ecommerce-v1'
        or len(bindings)!=1 or snapshot['canaryInstallations']!=0):raise ValueError('exact H installation required')
    b=bindings[0]
    if (str(b['generation'])!=G_GENERATION or b['revision']!=4 or b['execution_epoch']!=3
        or b['enabled'] is not True or b['operation_fence'] is not False
        or b['desired_state']!='enabled' or b['observed_state']!='ready' or b['config_ref']!=CONFIG):
        raise ValueError('exact ready H binding required')
    if (str(parent['receipt_id'])!=DETACH or parent['phase']!='detach'
        or parent['org_id']!='org-org' or parent['project_id']!='dev-project'
        or canonical_sha256(parent['authority_data'])!=parent['content_hash']):raise ValueError('exact parent detach required')
    return SuccessorDispatchRegistrationRequest.model_validate(dict(
        schemaVersion='aos.ecommerce.successor-dispatch-registration/v1',expectedGroupRevision=16,
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
    from a0v_ecommerce_diagnostic_reinstall import load_profile
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
    result=dict(outcome='CURRENT_H_SUCCESSOR_REGISTERED',request=material,receipt=receipt,replayed=replayed)
    path=STATE/'register-result.json'
    if not path.exists():freeze(path,result)
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['preview','register']);args=parser.parse_args()
    plane=setup();request=current_request()
    result=(dict(outcome='CURRENT_H_SUCCESSOR_REQUEST_PREVIEW',request=request.model_dump(mode='json',by_alias=True),requestHash=request.request_hash())
            if args.mode=='preview' else register(plane,request))
    print(json.dumps(result,ensure_ascii=False,indent=2,default=str))


if __name__=='__main__':main()

"""Fixed S successor registration after the formally detached/uninstalled Q."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT.parent/'.aos-recovery-20260917/state/q-advisor-baseline/replacement-s/registration'
S_ID='77b8e5c2-db96-4d55-a808-1b62e00163d2'
S_GENERATION='e621100a-baea-440f-9075-ae8a5290845a'
LOCK='sha256:15ac55d0ca7098c4df286ad70b6a20e79c327b0ec9c53baceea7cbb7059fcae8'
CONFIG={'configurationId':'d06d9d3e-da79-4e11-a476-b1d2ac19457e','revision':1,
        'hash':'sha256:42845fe9ebf7381cb20ff40323409de166abffab0a8c6c3917cc7bc180392fbe'}
Q_ID='9c49b383-e04d-41b4-8276-8b8bc6db49a8'
DETACH='2bcb4ff2-9da1-4bc8-a3b3-7ed98e18eb4d'
DETACH_HASH='sha256:cc974be8c9e22afeea41d3dd665c4f4b92c50899e245d2df0869d78658d11f5f'
GROUP='6a402d31-83ad-546c-807f-508c87498ce1'
KEY='a0v-qyh-clean-generation-s-successor-v1'
ACTOR='a0v-ecommerce-growth-1.4-runtime-owner'


def request_from(snapshot,parent,routes,q_head):
    from aos_api.ecommerce_growth_successor_registration import SuccessorDispatchRegistrationRequest
    from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
    from aos_api.asset_registry.canonical_json import canonical_sha256
    head,bindings=snapshot['head'],snapshot['bindings']
    if (str(head['installation_id'])!=S_ID or head['etag_version']!=5 or head['state']!='active'
        or head['lock_hash']!=LOCK or head['overlay_revision']!='a0v-canonical-ecommerce-v1'
        or len(bindings)!=1 or snapshot['canaryInstallations']!=0
        or len(snapshot['resources'])!=3
        or any(row['cleanup_state']!='pending' or row['observed_release'] is not False
               for row in snapshot['resources'])
        or len(snapshot['operations'])!=4
        or {row['kind'] for row in snapshot['operations']}!={'runtime-apply','runtime-verify','configure','enable'}
        or any(row['status']!='succeeded' for row in snapshot['operations'])):
        raise ValueError('exact live S installation required')
    binding=bindings[0]
    if (str(binding['generation'])!=S_GENERATION or binding['revision']!=4
        or binding['execution_epoch']!=3 or binding['enabled'] is not True
        or binding['operation_fence'] is not False or binding['desired_state']!='enabled'
        or binding['observed_state']!='ready' or binding['config_ref']!=CONFIG):
        raise ValueError('exact ready S binding required')
    if (str(q_head['installation_id'])!=Q_ID or q_head['state']!='uninstalled'
        or q_head['etag_version']!=6):
        raise ValueError('exact formally uninstalled Q required')
    if (str(parent['receipt_id'])!=DETACH or parent['phase']!='detach'
        or parent['org_id']!='org-org' or parent['project_id']!='dev-project'
        or parent['content_hash']!=DETACH_HASH
        or canonical_sha256(parent['authority_data'])!=DETACH_HASH):
        raise ValueError('exact final Q detach required')
    if (len(routes)!=len(ECOMMERCE_GROWTH_OPERATIONS)
        or [row['operation_id'] for row in routes]!=sorted(ECOMMERCE_GROWTH_OPERATIONS)
        or any(row['handler_kind']!='legacy' or row['installation_id'] is not None
               or row['generation'] is not None or row['execution_epoch'] is not None
               or row['operation_fence'] is not True or row['revision']!=32
               or row['cutover_group_revision']!=59 for row in routes)):
        raise ValueError('exact detached Q route group required')
    return SuccessorDispatchRegistrationRequest.model_validate({
        'schemaVersion':'aos.ecommerce.successor-dispatch-registration/v1',
        'expectedGroupRevision':59,
        'predecessorDetachReceiptRef':{'resourceType':'DispatchDisableDetachReceipt',
            'resourceId':DETACH,'revision':1,'contentHash':DETACH_HASH},
        'registration':{'schemaVersion':'aos.ecommerce.first-dispatch-registration/v1',
            'installationRef':{'installationId':S_ID,'revision':5,'lockHash':LOCK,
                'overlayRevision':head['overlay_revision']},
            'generation':S_GENERATION,'bindingRevision':4,'executionEpoch':3,
            'configRef':CONFIG,'groupId':GROUP,'idempotencyKey':KEY}})


def setup():
    sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT/'services/aos-api'))
    from a0v_event_complete_product_api import load_launcher
    if load_launcher().preflight()['outcome']!='CONTROLLED_API_LOCAL_DIAGNOSTIC_PREFLIGHT_GREEN':
        raise ValueError('controlled identity preflight required')
    import os
    os.environ['AOS_EXTENSION_RUNTIME_HOST_ENABLED']='0'
    from aos_api.asset_registry.control_wiring import build_runtime_control_plane
    from aos_api.ecommerce_growth_registration_connection import registration_connection
    return build_runtime_control_plane(registration_connect=registration_connection)


def current_request():
    import a0v_r_replacement_install as recovery
    from a0v_formal_text_model_renewal import database_connect
    current=recovery.load_profile();snapshot=current.observe_installation(S_ID)
    q=current.observe_installation(Q_ID)
    with database_connect('aos_meta_head')() as conn:
        parent=conn.execute('''SELECT org_id,project_id,receipt_id,phase,authority_data,content_hash
          FROM extension_dispatch_lifecycle_receipt WHERE org_id='org-org' AND project_id='dev-project'
          AND receipt_id=%s''',(DETACH,)).fetchone()
        routes=[dict(row) for row in conn.execute('''SELECT operation_id,handler_kind,installation_id,
          generation,execution_epoch,operation_fence,revision,cutover_group_revision
          FROM extension_operation_dispatch_binding WHERE org_id='org-org' AND project_id='dev-project'
          AND cutover_group_id=%s ORDER BY operation_id''',(GROUP,)).fetchall()]
        inflight=dict(conn.execute('''SELECT
          (SELECT count(*) FROM extension_runtime_execution_attempt WHERE org_id='org-org'
            AND project_id='dev-project' AND state='running') running,
          (SELECT count(*) FROM automation_occurrence_dispatch_attempt a JOIN automation_occurrence o
            USING(org_id,project_id,occurrence_id) WHERE a.org_id='org-org' AND a.project_id='dev-project'
            AND a.status IN ('claimed','unknown')) unresolved''').fetchone())
    if parent is None or inflight!={'running':0,'unresolved':0}:
        raise ValueError('final Q detach and drained tenant required')
    return request_from(snapshot,dict(parent),routes,q['head'])


def register(plane,request):
    from aos_api.tenant_scope import TenantScope
    from a0v_qyh_current_product_event_first_chain import freeze,freeze_or_match
    service=plane.first_dispatch_registration_service;scope=TenantScope('org-org','dev-project')
    intent=STATE/'register-intent.json';material=request.model_dump(mode='json',by_alias=True)
    existed=intent.exists();freeze_or_match(intent,material)
    if existed:
        receipt=service.read_successor_receipt(scope=scope,installation_id=S_ID,
            idempotency_key=KEY,actor=ACTOR);replayed=True
    else:
        receipt=service.register_successor(scope=scope,request=request,actor=ACTOR)
        replayed=receipt['replayed']
    if not receipt or receipt['requestHash']!=request.request_hash():
        raise ValueError('exact S registered request readback required')
    result={'outcome':'CURRENT_S_SUCCESSOR_REGISTERED','request':material,
            'receipt':receipt,'replayed':replayed}
    path=STATE/'register-result.json'
    if not path.exists():freeze(path,result)
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['preview','register']);args=parser.parse_args()
    plane=setup();request=current_request()
    result=({'outcome':'CURRENT_S_SUCCESSOR_REQUEST_PREVIEW',
             'request':request.model_dump(mode='json',by_alias=True),
             'requestHash':request.request_hash()}
            if args.mode=='preview' else register(plane,request))
    print(json.dumps(result,ensure_ascii=False,indent=2,default=str))


if __name__=='__main__':main()

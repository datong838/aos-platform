"""Fixed local pristine-registration acceptance via current production Owners."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services/aos-api'))
os.environ['AOS_DOTENV_DISABLED']='1'
from aos_api.ecommerce_growth_registration_contracts import FirstDispatchRegistrationRequest
from aos_api.ecommerce_growth_registration_withdrawal import RegistrationWithdrawalRequest
from aos_api.tenant_scope import TenantScope

INSTALLATION='97aeb2e7-59ba-40f6-89a3-fb0293bc0497'
GENERATION='3a445eee-aa28-4459-9e5a-f12a806a94b1'
ACTOR='a0v-ecommerce-growth-1.4-runtime-owner'
KEY='a0v-qyh-reboot-first-registration-acceptance-v1'
STATE=ROOT.parent/'.aos-recovery-20260913/state/qyh-registration-acceptance-v1'
SCOPE=TenantScope('org-org','dev-project')
TASK_ID='A0V-QYH-REGISTRATION-CYCLE-20260913'
PREDECESSOR_WITHDRAWAL_KEY=None


def freeze(path,body):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as stream:
        json.dump(body,stream,ensure_ascii=False,indent=2)
        stream.flush();os.fsync(stream.fileno())
    directory=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(directory)
    finally:os.close(directory)


def saved_request(state):
    path=state/'request.json'
    if path.is_symlink():raise ValueError('REGISTRATION_STATE_SYMLINK')
    request=FirstDispatchRegistrationRequest.model_validate(json.loads(path.read_text()))
    if (request.installationRef.installation_id!=INSTALLATION or request.generation!=GENERATION
            or request.idempotencyKey!=KEY):raise ValueError('REGISTRATION_FIXED_TARGET_DRIFT')
    return request


def require_predecessor(owner,status):
    if PREDECESSOR_WITHDRAWAL_KEY is None:
        if status['state']!='unregistered':raise ValueError('REGISTRATION_ALREADY_EXISTS')
        return
    if status['state']!='withdrawn':raise ValueError('REGISTRATION_PREDECESSOR_REQUIRED')
    previous=owner.read_withdrawal_receipt(scope=SCOPE,installation_id=INSTALLATION,
        idempotency_key=PREDECESSOR_WITHDRAWAL_KEY,actor=ACTOR)
    if status['withdrawalReceiptId']!=previous['receiptId']:
        raise ValueError('REGISTRATION_PREDECESSOR_DRIFT')


def prepare(owner,state):
    if (state/'request.json').exists():raise FileExistsError('registration request already frozen')
    with owner._transaction(SCOPE) as conn:
        rows=conn.execute('''SELECT i.etag_version,r.lock_hash,r.overlay_revision,
            b.generation,b.revision,b.execution_epoch,b.config_ref
            FROM public.bundle_installation i
            JOIN public.bundle_installation_revision r ON r.org_id=i.org_id AND r.project_id=i.project_id
              AND r.installation_pk=i.installation_pk AND r.revision=i.current_revision
            JOIN public.extension_runtime_binding b ON b.org_id=i.org_id AND b.project_id=i.project_id
              AND b.installation_id=i.installation_id
            WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s''',(*SCOPE.key,INSTALLATION)).fetchall()
        if len(rows)!=1 or str(rows[0]['generation'])!=GENERATION:
            raise ValueError('REGISTRATION_FIXED_TARGET_DRIFT')
        row=rows[0]
        request=FirstDispatchRegistrationRequest(schemaVersion='aos.ecommerce.first-dispatch-registration/v1',
            installationRef=dict(installationId=INSTALLATION,revision=row['etag_version'],
                                 lockHash=row['lock_hash'],overlayRevision=row['overlay_revision']),
            generation=GENERATION,bindingRevision=row['revision'],executionEpoch=row['execution_epoch'],
            configRef=row['config_ref'],groupId=str(uuid4()),idempotencyKey=KEY)
        result=owner.validate_current_authority_in_transaction(conn,scope=SCOPE,request=request,actor=ACTOR)
    status=owner.registration_status(scope=SCOPE,installation_id=INSTALLATION,actor=ACTOR)
    require_predecessor(owner,status)
    freeze(state/'request.json',request.model_dump(mode='json',by_alias=True))
    return result


def execute(action,owner,state=None):
    state=Path(STATE if state is None else state)
    if action=='prepare':return prepare(owner,state)
    if action=='status':return owner.registration_status(scope=SCOPE,installation_id=INSTALLATION,actor=ACTOR)
    request=saved_request(state)
    if action=='register':
        freeze(state/'register-intent.json',{'requestHash':request.request_hash()})
        result=owner.register(scope=SCOPE,request=request,actor=ACTOR)
        freeze(state/'register-result.json',result)
        return result
    if action=='read':
        return owner.read_receipt(scope=SCOPE,installation_id=INSTALLATION,idempotency_key=request.idempotencyKey,actor=ACTOR)
    if action=='withdraw':
        status=owner.registration_status(scope=SCOPE,installation_id=INSTALLATION,actor=ACTOR)
        if status['state']!='registered' or status['allowedActions']!=['withdraw']:
            raise ValueError('REGISTRATION_NOT_PRISTINE')
        origin=owner.read_receipt(scope=SCOPE,installation_id=INSTALLATION,
                                  idempotency_key=request.idempotencyKey,actor=ACTOR)
        expected=dict(resourceType='FirstDispatchRegistrationReceipt',revision=1,
                      resourceId=origin['receiptId'],contentHash=origin['contentHash'])
        if (status['registrationReceiptRef']!=expected or origin['groupId']!=request.groupId
                or origin['requestHash']!=request.request_hash()):
            raise ValueError('REGISTRATION_WITHDRAW_ORIGIN_DRIFT')
        withdrawal=RegistrationWithdrawalRequest(registrationReceiptRef=status['registrationReceiptRef'],
            expectedInstallationEtag=status['expectedInstallationEtag'],idempotencyKey=KEY+'-withdraw')
        freeze(state/'withdraw-request.json',withdrawal.model_dump(mode='json',by_alias=True))
        freeze(state/'withdraw-intent.json',{'request':withdrawal.model_dump(mode='json',by_alias=True)})
        result=owner.withdraw(scope=SCOPE,installation_id=INSTALLATION,request=withdrawal,actor=ACTOR)
        freeze(state/'withdraw-result.json',result)
        return result
    if action=='read-withdrawal':
        return owner.read_withdrawal_receipt(scope=SCOPE,installation_id=INSTALLATION,
            idempotency_key=KEY+'-withdraw',actor=ACTOR)
    raise ValueError('REGISTRATION_ACTION_INVALID')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('prepare','register','read','status','withdraw','read-withdrawal'))
    args=parser.parse_args()
    leases=json.loads((ROOT.parent/'docs/palantier/AOS项目开发上下文/memory/leases.json').read_text())['leases']
    lease=next(x for x in leases if x['task_id']==TASK_ID)
    if (lease['owner']!='m1' or lease['status']!='ACTIVE'
            or datetime.fromisoformat(lease['lease_expires_at'])<=datetime.now(timezone.utc)
            or subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()!='m1'):
        raise ValueError('REGISTRATION_CYCLE_LEASE_REQUIRED')
    from a0v_product_controlled_api import load_launcher
    load_launcher().configure_environment()
    from aos_api.ecommerce_growth_registration_connection import registration_connection
    from aos_api.asset_registry.control_wiring import build_runtime_control_plane
    owner=build_runtime_control_plane(registration_connect=registration_connection).first_dispatch_registration_service
    print(json.dumps(execute(args.action,owner,state=STATE),ensure_ascii=False,default=str,indent=2))


if __name__=='__main__':main()

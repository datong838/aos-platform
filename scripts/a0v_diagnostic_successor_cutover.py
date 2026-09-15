"""Exact internal H cutover; unknown phase outcomes are read-only inspected."""
import argparse
import json
from pathlib import Path
import a0v_diagnostic_successor_business as f

STATE=f.STATE/'cutover'
OPERATION='2e355433-7e7a-52e0-b525-b61b7df5cfe8'
PREFIX='a0v-qyh-event-complete-generation-h-cutover-v1'
RECEIPT='85fd4c05-0729-4834-adf9-6cc17f475e57'
RECEIPT_HASH='sha256:f5e0d07df07adba05ca4d79629fa39cbc48ddb3fd09a82b7c16543050908ea99'


def load(phase):
    path=STATE/(phase+'-result.json')
    if not path.is_file() or path.stat().st_mode & 0o777!=0o600:raise ValueError('private prior result required')
    return json.loads(path.read_text())


def target(registration):
    from aos_api.ecommerce_growth_successor_registration import SuccessorDispatchRegistrationRequest
    from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
    from aos_api.asset_registry.canonical_json import canonical_sha256
    request=SuccessorDispatchRegistrationRequest.model_validate(registration['request'])
    receipt=registration['receipt'];inner=request.registration
    if (registration['outcome']!='CURRENT_H_SUCCESSOR_REGISTERED'
        or receipt['receiptId']!=RECEIPT or receipt['contentHash']!=RECEIPT_HASH
        or receipt['requestHash']!=request.request_hash()
        or inner.installationRef.installation_id!=f.G_ID or inner.generation!=f.G_GENERATION
        or inner.bindingRevision!=4 or inner.executionEpoch!=3 or inner.groupId!=f.GROUP
        or request.expectedGroupRevision!=16):raise ValueError('exact H registered target required')
    policy=dict(schemaVersion='aos.runtime-cutover-policy/v1',policyId='qyh-event-complete-generation-h-activation',revision=1,
        tenant=dict(orgId='org-org',projectId='dev-project'),targetInstallationId=f.G_ID,
        externalEffectsAllowed=False,fallbackAllowed=False,checkpoint=dict(legacyEntry='canonical-router',version=1))
    value=dict(cutoverGroupId=f.GROUP,expectedGroupRevision=16,targetInstallationId=f.G_ID,targetGeneration=f.G_GENERATION,
        targetExecutionEpoch=3,targetRuntimeRevision=4,operationIds=sorted(ECOMMERCE_GROWTH_OPERATIONS),
        policyRef=dict(resourceType='RuntimeCutoverPolicyRevision',resourceId=policy['policyId'],revision=1,contentHash=canonical_sha256(policy)),
        registrationReceiptRef=dict(resourceType='SuccessorDispatchRegistrationReceipt',resourceId=RECEIPT,revision=1,contentHash=RECEIPT_HASH))
    return value,policy


def exact_ref(phase,kind):
    receipt=load(phase)['receipt']
    if receipt['cutoverOperationId']!=OPERATION:raise ValueError('prior operation differs')
    return dict(resourceType=kind,resourceId=receipt['receiptId'],revision=1,contentHash=receipt['contentHash'])


def invoke(phase,plane):
    from aos_api.tenant_scope import TenantScope
    from aos_api.ecommerce_growth_cutover import CutoverPrepareRequest,CutoverCommitRequest,CutoverFinalizeRequest,CutoverExactRef
    from a0v_qyh_current_product_event_first_chain import freeze,freeze_or_match,_approve
    scope=TenantScope('org-org','dev-project');service=plane.ecommerce_growth_cutover_service
    if phase=='inspect':
        return service.read_activation_history(scope=scope,installation_id=f.G_ID,idempotency_key=PREFIX+'-prepare',actor=f.ACTOR)
    intent=STATE/(phase+'-intent.json')
    if intent.exists():raise ValueError('existing phase intent: inspect history, never resend')
    if phase=='approve':
        registration=json.loads((f.STATE/'register-result.json').read_text())
        payload,policy=target(registration)
        current=plane.first_dispatch_registration_service.read_successor_receipt(scope=scope,installation_id=f.G_ID,idempotency_key=f.KEY,actor=f.ACTOR)
        if current['contentHash']!=RECEIPT_HASH:raise ValueError('live successor receipt differs')
        freeze_or_match(STATE/'policy.json',policy);freeze(intent,payload)
        bundle,ref=_approve('ecommerce_growth_cutover',payload,PREFIX+'-approval')
        result=dict(proposalId=bundle.proposal.id,approvalRef=ref,payload=payload)
    else:
        extra={}
        if phase=='prepare':
            approved=load('approve')
            request=CutoverPrepareRequest(cutoverOperationId=OPERATION,idempotencyKey=PREFIX+'-prepare',
                approvalRef={k:v for k,v in approved['approvalRef'].items() if k!='receiptId'},
                checkpoint=dict(legacyEntry='canonical-router',version=1),occurrenceWatermark=None,pendingTargetReceiptRefs=[],
                **{k:v for k,v in approved['payload'].items() if k!='operationIds'})
            method=service.prepare_activation
        elif phase in ('pause','commit'):
            request=CutoverCommitRequest(cutoverOperationId=OPERATION,idempotencyKey=PREFIX+'-commit',prepareReceiptRef=exact_ref('prepare','CutoverPrepareReceipt'))
            method=service.begin_activation_commit if phase=='pause' else service.commit_activation
        elif phase in ('validate','resume'):
            request=CutoverFinalizeRequest(cutoverOperationId=OPERATION,idempotencyKey=PREFIX+'-finalize',commitReceiptRef=exact_ref('commit','CutoverCommitReceipt'))
            method=service.validate_activation if phase=='validate' else service.resume_activation
            if phase=='resume':extra['validate_receipt_ref']=CutoverExactRef(**exact_ref('validate','CutoverValidateReceipt'))
        else:raise ValueError('unknown phase')
        freeze(intent,dict(request=request.model_dump(mode='json',by_alias=True),**{k:v.model_dump(mode='json',by_alias=True) for k,v in extra.items()}))
        receipt=method(scope,request,actor=f.ACTOR,**extra)
        result=dict(receipt=receipt.model_dump(mode='json',by_alias=True))
    result['outcome']='CURRENT_H_CUTOVER_'+phase.upper()
    freeze(STATE/(phase+'-result.json'),result)
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['approve','prepare','pause','commit','validate','resume','inspect'])
    args=parser.parse_args();plane=f.setup()
    print(json.dumps(invoke(args.phase,plane),ensure_ascii=False,indent=2,default=str))


if __name__=='__main__':main()

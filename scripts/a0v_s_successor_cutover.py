"""Exact internal S cutover; existing phase intents are inspected, never resent."""
import argparse
import json

import a0v_s_successor_business as successor

STATE=successor.STATE.parent/'cutover'
OPERATION='eea1d47d-6bc3-5972-b1f2-5a30430ce7bd'
PREFIX='a0v-qyh-clean-generation-s-cutover-v1'


def load(phase):
    path=STATE/f'{phase}-result.json'
    if not path.is_file() or path.stat().st_mode & 0o777!=0o600:
        raise ValueError('private prior result required')
    return json.loads(path.read_text())


def registration_result():
    path=successor.STATE/'register-result.json'
    if not path.is_file() or path.stat().st_mode & 0o777!=0o600:
        raise ValueError('private Q registration required')
    return json.loads(path.read_text())


def target(registration):
    from aos_api.ecommerce_growth_successor_registration import SuccessorDispatchRegistrationRequest
    from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
    from aos_api.asset_registry.canonical_json import canonical_sha256
    request=SuccessorDispatchRegistrationRequest.model_validate(registration['request'])
    receipt=registration['receipt'];inner=request.registration
    if (registration['outcome']!='CURRENT_S_SUCCESSOR_REGISTERED'
        or receipt['requestHash']!=request.request_hash()
        or str(inner.installationRef.installation_id)!=successor.S_ID
        or str(inner.generation)!=successor.S_GENERATION or inner.bindingRevision!=4
        or inner.executionEpoch!=3 or str(inner.groupId)!=successor.GROUP
        or request.expectedGroupRevision!=59):
        raise ValueError('exact S registered target required')
    policy={'schemaVersion':'aos.runtime-cutover-policy/v1',
        'policyId':'qyh-clean-generation-s-activation','revision':1,
        'tenant':{'orgId':'org-org','projectId':'dev-project'},
        'targetInstallationId':successor.S_ID,'externalEffectsAllowed':False,
        'fallbackAllowed':False,'checkpoint':{'legacyEntry':'canonical-router','version':1}}
    value={'cutoverGroupId':successor.GROUP,'expectedGroupRevision':59,
        'targetInstallationId':successor.S_ID,'targetGeneration':successor.S_GENERATION,
        'targetExecutionEpoch':3,'targetRuntimeRevision':4,
        'operationIds':sorted(ECOMMERCE_GROWTH_OPERATIONS),
        'policyRef':{'resourceType':'RuntimeCutoverPolicyRevision',
            'resourceId':policy['policyId'],'revision':1,'contentHash':canonical_sha256(policy)},
        'registrationReceiptRef':{'resourceType':'SuccessorDispatchRegistrationReceipt',
            'resourceId':receipt['receiptId'],'revision':1,'contentHash':receipt['contentHash']}}
    return value,policy


def exact_ref(phase,kind):
    receipt=load(phase)['receipt']
    if receipt['cutoverOperationId']!=OPERATION:raise ValueError('prior operation differs')
    return {'resourceType':kind,'resourceId':receipt['receiptId'],'revision':1,
            'contentHash':receipt['contentHash']}


def invoke(phase,plane):
    from aos_api.tenant_scope import TenantScope
    from aos_api.ecommerce_growth_cutover import (
        CutoverPrepareRequest,CutoverCommitRequest,CutoverFinalizeRequest,CutoverExactRef)
    from a0v_qyh_current_product_event_first_chain import freeze,freeze_or_match,_approve
    scope=TenantScope('org-org','dev-project');service=plane.ecommerce_growth_cutover_service
    if phase=='inspect':
        return service.read_activation_history(scope=scope,installation_id=successor.S_ID,
            idempotency_key=PREFIX+'-prepare',actor=successor.ACTOR)
    intent=STATE/f'{phase}-intent.json'
    if intent.exists():raise ValueError('existing phase intent: inspect history, never resend')
    if phase=='approve':
        registration=registration_result();payload,policy=target(registration)
        current=plane.first_dispatch_registration_service.read_successor_receipt(
            scope=scope,installation_id=successor.S_ID,idempotency_key=successor.KEY,
            actor=successor.ACTOR)
        if (current['receiptId']!=registration['receipt']['receiptId']
            or current['contentHash']!=registration['receipt']['contentHash']):
            raise ValueError('live S successor receipt differs')
        freeze_or_match(STATE/'policy.json',policy);freeze(intent,payload)
        bundle,ref=_approve('ecommerce_growth_cutover',payload,PREFIX+'-approval')
        result={'proposalId':bundle.proposal.id,'approvalRef':ref,'payload':payload}
    else:
        extra={}
        if phase=='prepare':
            approved=load('approve')
            request=CutoverPrepareRequest(cutoverOperationId=OPERATION,
                idempotencyKey=PREFIX+'-prepare',
                approvalRef={key:value for key,value in approved['approvalRef'].items()
                             if key!='receiptId'},
                checkpoint={'legacyEntry':'canonical-router','version':1},
                occurrenceWatermark=None,pendingTargetReceiptRefs=[],
                **{key:value for key,value in approved['payload'].items()
                   if key!='operationIds'})
            method=service.prepare_activation
        elif phase in ('pause','commit'):
            request=CutoverCommitRequest(cutoverOperationId=OPERATION,
                idempotencyKey=PREFIX+'-commit',
                prepareReceiptRef=exact_ref('prepare','CutoverPrepareReceipt'))
            method=service.begin_activation_commit if phase=='pause' else service.commit_activation
        elif phase in ('validate','resume'):
            request=CutoverFinalizeRequest(cutoverOperationId=OPERATION,
                idempotencyKey=PREFIX+'-finalize',
                commitReceiptRef=exact_ref('commit','CutoverCommitReceipt'))
            method=service.validate_activation if phase=='validate' else service.resume_activation
            if phase=='resume':
                extra['validate_receipt_ref']=CutoverExactRef(
                    **exact_ref('validate','CutoverValidateReceipt'))
        else:raise ValueError('unknown phase')
        freeze(intent,{'request':request.model_dump(mode='json',by_alias=True),
            **{key:value.model_dump(mode='json',by_alias=True) for key,value in extra.items()}})
        receipt=method(scope,request,actor=successor.ACTOR,**extra)
        result={'receipt':receipt.model_dump(mode='json',by_alias=True)}
    result['outcome']=f'CURRENT_S_CUTOVER_{phase.upper()}'
    freeze(STATE/f'{phase}-result.json',result)
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=[
        'approve','prepare','pause','commit','validate','resume','inspect'])
    args=parser.parse_args();plane=successor.setup()
    print(json.dumps(invoke(args.phase,plane),ensure_ascii=False,indent=2,default=str))


if __name__=='__main__':main()

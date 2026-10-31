from datetime import timedelta
import hashlib
import json
from uuid import UUID

import pytest

from aos_api.aip_budget_reservation_contracts import BudgetExactRef
from aos_api.aip_model_route_eval_finalization_proof import (
    RouteEvalFinalizationConflict,RouteEvalFinalizationProof,
    RouteEvalFinalizationProofStore,RouteEvalFinalizedCallProof,
    canonical_route_eval_finalization_proof,
)
from aos_api.aip_model_route_eval_execution_journal import (
    RouteEvalExecutionCommand,RouteEvalExecutionResult,_canonical,
)
from aos_api.aip_budget_reservation_contracts import ReserveBudgetRequest,exact_ref_payload
from aos_api.tenant_scope import TenantScope
from aos_api.aip_model_runtime_store import canonical_hash
from test_model_route_eval_manifest import NOW
from test_model_route_eval_signatures import presented_bundle_inputs


TARGET_ID=UUID('11111111-1111-4111-8111-111111111111')
JUDGE_ID=UUID('22222222-2222-4222-8222-222222222222')


def ref(kind,ident,revision=1):
    return BudgetExactRef(resourceType=kind,resourceId=ident,revision=revision,
        contentHash='sha256:'+hashlib.sha256((kind+ident+str(revision)).encode()).hexdigest())


def call(item,reservation_id,*,target_call_key=None):
    claim=item.envelope.claim
    return RouteEvalFinalizedCallProof(
        tenant=claim.tenant,executionId=claim.execution_id,caseId=claim.case_id,
        purpose=claim.purpose,callKey='call-'+claim.purpose,
        targetCallKey=target_call_key,reservationId=reservation_id,
        commandHash='a'*64,resultHash='b'*64,
        approvalRef=ref('ActionApprovalEvent','approval-'+claim.purpose),
        reservationRef=ref('BudgetReservationRevision',str(reservation_id)),
        providerRequestRef=ref('CapabilityProviderRequestReceipt','request-'+claim.purpose),
        providerResultId='result-'+claim.purpose,
        signedCertificate=item.certificate_envelope,signedCase=item.envelope,
        issuerInput=item.issuer_input,
        certificateHash=canonical_hash(item.certificate_envelope.model_dump(
            mode='json',by_alias=True)),
        caseEnvelopeHash=canonical_hash(item.envelope.model_dump(
            mode='json',by_alias=True)),
        issuerInputHash=canonical_hash(item.issuer_input.model_dump(
            mode='json',by_alias=True)),
        usageReceiptRefs=[ref('UsageReceipt','usage-'+claim.purpose+'-in'),
            ref('UsageReceipt','usage-'+claim.purpose+'-out')],
        budgetRevision=3,actualMinor=2,executionAllowed=False)


def bundle():
    manifest,target,judge=presented_bundle_inputs()
    target_call=call(target,TARGET_ID)
    judge_call=call(judge,JUDGE_ID,target_call_key=target_call.call_key)
    value=RouteEvalFinalizationProof(tenant=target.envelope.claim.tenant,
        executionId=target.envelope.claim.execution_id,
        manifestHash=hashlib.sha256(manifest).hexdigest(),
        contextBindingHash=target.envelope.claim.context_binding_hash,
        admissionHash='c'*64,runId='run',reportId='report',reportRevision=1,
        reportHash='d'*64,calls=(target_call,judge_call),
        finalizedAt=NOW+timedelta(seconds=3),executionAllowed=False)
    return value,manifest,target,judge


def proof():return bundle()[0]


def test_complete_route_finalization_proof_is_canonical_and_paired():
    value=proof();text,digest=canonical_route_eval_finalization_proof(value)
    assert len(text)>100 and len(digest)==64
    assert [(c.case_id,c.purpose) for c in value.calls]==[
        ('case','target'),('case','judge')]
    assert all(c.execution_allowed is False for c in value.calls)


@pytest.mark.parametrize('fault',['target_key','duplicate_usage','usage_type',
    'budget_revision','actual','certificate_hash','case_hash','issuer_hash',
    'execution','manifest','context','pair','reservation'])
def test_route_finalization_proof_rejects_cross_call_or_persistent_drift(fault):
    value=proof();target,judge=value.calls
    if fault=='target_key':judge=judge.model_copy(update={'target_call_key':'other'})
    elif fault=='duplicate_usage':judge=judge.model_copy(update={
        'usage_receipt_refs':(judge.usage_receipt_refs[0],)*2})
    elif fault=='usage_type':judge=judge.model_copy(update={'usage_receipt_refs':(
        ref('Evidence','wrong'),judge.usage_receipt_refs[1])})
    elif fault=='budget_revision':judge=judge.model_copy(update={'budget_revision':1})
    elif fault=='actual':judge=judge.model_copy(update={'actual_minor':-1})
    elif fault=='certificate_hash':judge=judge.model_copy(update={'certificate_hash':'0'*64})
    elif fault=='case_hash':judge=judge.model_copy(update={'case_envelope_hash':'0'*64})
    elif fault=='issuer_hash':judge=judge.model_copy(update={'issuer_input_hash':'0'*64})
    elif fault=='execution':judge=judge.model_copy(update={'execution_id':'other'})
    elif fault=='manifest':value=value.model_copy(update={'manifest_hash':'0'*64})
    elif fault=='context':value=value.model_copy(update={'context_binding_hash':'0'*64})
    elif fault=='pair':target=target.model_copy(update={'case_id':'other'})
    else:judge=judge.model_copy(update={'reservation_id':target.reservation_id})
    value=value.model_copy(update={'calls':(target,judge)})
    with pytest.raises((RouteEvalFinalizationConflict,ValueError)):
        canonical_route_eval_finalization_proof(value)


class FakeJournal:
    def __init__(self,value,presented):
        self.items={}
        for item,witness in zip(value.calls,presented,strict=True):
            request=ReserveBudgetRequest(operationId='aip_route_eval_'+item.purpose+'_call',
                invocationKey=item.call_key,taskRef=ref('Task','task'),
                policyRef=ref('BudgetRevision','budget'),
                pricingRef=ref('ModelPriceSnapshotRevision','price'),
                approvalRef=item.approval_ref,currency='CNY',upperBoundMinor=3)
            command=RouteEvalExecutionCommand(tenant=item.tenant,
                executionId=item.execution_id,manifestHash=value.manifest_hash,
                contextBindingHash=value.context_binding_hash,
                admissionHash=value.admission_hash,callKey=item.call_key,
                callBindingHash=item.signed_case.claim.call_binding_hash,
                caseId=item.case_id,purpose=item.purpose,
                targetCallKey=item.target_call_key,budgetRequest=request,
                invocationRef=ref('CapabilityInvocationRevision','invocation-'+item.purpose),
                reservationRef=item.reservation_ref,
                inputHash=hashlib.sha256(witness.input_bytes).hexdigest(),executionAllowed=False)
            result=RouteEvalExecutionResult(tenant=item.tenant,
                executionId=item.execution_id,callKey=item.call_key,caseId=item.case_id,
                purpose=item.purpose,providerRequestRef=item.provider_request_ref,
                providerResultId=item.provider_result_id,providerId='provider',modelId='model',
                outputHash=hashlib.sha256(witness.output_bytes).hexdigest(),
                promptTokens=3,completionTokens=4,observedAt=NOW+timedelta(seconds=2),
                executionAllowed=False)
            _,command_hash=_canonical(command);_,result_hash=_canonical(result)
            item.command_hash=command_hash;item.result_hash=result_hash
            self.items[item.reservation_id]={'command':command,'inputBytes':witness.input_bytes,
                'result':result,'outputBytes':witness.output_bytes}
    def read(self,conn,scope,reservation_id):return self.items.get(reservation_id)


class Rows:
    def __init__(self,one=None,many=None):self.one=one;self.many=many
    def fetchone(self):return self.one
    def fetchall(self):return self.many or []


class ProofConnection:
    def __init__(self,value):
        self.value=value;self.header=None;self.material=None;self.calls=[];self.sql=[]
        self.budgets={item.reservation_id:{'state':'settled','revision':item.budget_revision,
            'actual_minor':item.actual_minor,
            'usage_receipt_refs':[exact_ref_payload(r) for r in item.usage_receipt_refs],
            'provider_request_receipt_ref':exact_ref_payload(item.provider_request_ref)}
            for item in value.calls}
    def execute(self,sql,params=()):
        text=' '.join(str(sql).split());self.sql.append(text)
        assert text.startswith(('SELECT ','INSERT '))
        if 'FROM public.aip_budget_reservation' in text:return Rows(self.budgets.get(params[-1]))
        if 'FROM public.aip_eval_run r' in text:return Rows({'status':'succeeded','content_hash':self.value.report_hash})
        if 'FROM public.aip_route_eval_release_material' in text:return Rows(self.material)
        if 'FROM public.aip_route_eval_finalization_proof' in text:return Rows(self.header)
        if 'FROM public.aip_route_eval_finalized_call_proof' in text:return Rows(many=list(self.calls))
        if text.startswith('INSERT INTO public.aip_route_eval_finalization_proof'):
            (org,project,execution,proof_hash,payload,manifest,context,admission,run,
             report,revision,report_hash,finalized)=params
            self.header={'org_id':org,'project_id':project,'execution_id':execution,
                'proof_hash':proof_hash,'proof_payload':json.loads(payload),
                'manifest_hash':manifest,'context_binding_hash':context,
                'admission_hash':admission,'run_id':run,'report_id':report,
                'report_revision':revision,'report_hash':report_hash,'finalized_at':finalized}
            return Rows()
        if text.startswith('INSERT INTO public.aip_route_eval_release_material'):
            org,project,execution,manifest_hash,manifest_payload=params
            self.material={'org_id':org,'project_id':project,'execution_id':execution,
                'manifest_hash':manifest_hash,'manifest_payload':bytes(manifest_payload)}
            return Rows()
        if text.startswith('INSERT INTO public.aip_route_eval_finalized_call_proof'):
            org,project,execution,case,purpose,reservation,call_key,digest,payload=params
            self.calls.append({'org_id':org,'project_id':project,'execution_id':execution,
                'case_id':case,'purpose':purpose,'reservation_id':reservation,
                'call_key':call_key,'call_proof_hash':digest,
                'call_proof_payload':json.loads(payload)})
            return Rows()
        raise AssertionError('unexpected SQL: '+text)
    def commit(self):raise AssertionError('proof store cannot commit')
    rollback=commit


def finalization_fixture():
    value,manifest,target,judge=bundle();journal=FakeJournal(value,(target,judge))
    # Journal hashes are persisted facts and therefore belong in the final proof.
    value=RouteEvalFinalizationProof.model_validate(value.model_dump(mode='json',by_alias=True))
    return value,manifest,target,judge,journal


def test_finalization_store_persists_reads_and_exactly_replays_without_committing():
    value,manifest,target,judge,journal=finalization_fixture();conn=ProofConnection(value)
    store=RouteEvalFinalizationProofStore(journal=journal);scope=TenantScope('org-org','dev-project')
    args=dict(manifest_bytes=manifest,presented_cases=(target,judge),
        checked_at=NOW+timedelta(seconds=2),revoked_identity_ids=frozenset())
    assert store.persist(conn,scope,value,**args)==value
    assert store.read(conn,scope,value.execution_id)==value
    assert store.persist(conn,scope,value,**args)==value
    assert len(conn.header)==13 and len(conn.calls)==2
    assert conn.material=={'org_id':'org-org','project_id':'dev-project',
        'execution_id':value.execution_id,'manifest_hash':value.manifest_hash,
        'manifest_payload':manifest}
    assert all(sql.startswith(('SELECT ','INSERT ')) for sql in conn.sql)
    assert all('FOR SHARE' not in sql for sql in conn.sql)


@pytest.mark.parametrize('fault',['journal','budget','run','stored'])
def test_finalization_store_rejects_incomplete_or_drifted_authority(fault):
    value,manifest,target,judge,journal=finalization_fixture();conn=ProofConnection(value)
    store=RouteEvalFinalizationProofStore(journal=journal);scope=TenantScope('org-org','dev-project')
    if fault=='journal':journal.items[value.calls[0].reservation_id]['outputBytes']=b'wrong'
    elif fault=='budget':conn.budgets[value.calls[0].reservation_id]['state']='submitted'
    elif fault=='run':value=value.model_copy(update={'report_hash':'e'*64})
    else:
        store.persist(conn,scope,value,manifest_bytes=manifest,presented_cases=(target,judge),
            checked_at=NOW+timedelta(seconds=2),revoked_identity_ids=frozenset())
        conn.calls[0]['call_proof_hash']='0'*64
        with pytest.raises(RouteEvalFinalizationConflict):store.read(conn,scope,value.execution_id)
        return
    with pytest.raises(RouteEvalFinalizationConflict):
        store.persist(conn,scope,value,manifest_bytes=manifest,presented_cases=(target,judge),
            checked_at=NOW+timedelta(seconds=2),revoked_identity_ids=frozenset())


@pytest.mark.parametrize('fault',['missing','payload','hash'])
def test_finalization_store_replay_requires_exact_immutable_release_material(fault):
    value,manifest,target,judge,journal=finalization_fixture();conn=ProofConnection(value)
    store=RouteEvalFinalizationProofStore(journal=journal);scope=TenantScope('org-org','dev-project')
    args=dict(manifest_bytes=manifest,presented_cases=(target,judge),
        checked_at=NOW+timedelta(seconds=2),revoked_identity_ids=frozenset())
    assert store.persist(conn,scope,value,**args)==value
    if fault=='missing':conn.material=None
    elif fault=='payload':conn.material['manifest_payload']=manifest+b'\n'
    else:conn.material['manifest_hash']='0'*64
    with pytest.raises(RouteEvalFinalizationConflict):
        store.persist(conn,scope,value,**args)

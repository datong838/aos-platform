from datetime import datetime,timezone
import hashlib
import json
from uuid import UUID

import pytest

from aos_api.aip_budget_reservation_contracts import (
    BudgetExactRef,ReserveBudgetRequest,
)
from aos_api.aip_budget_reservation_store import AipBudgetReservationStore
from aos_api.aip_model_route_eval_execution_journal import (
    RouteEvalExecutionCommand,RouteEvalExecutionConflict,
    RouteEvalExecutionJournal,RouteEvalExecutionResult,
)
from aos_api.tenant_scope import TenantScope


NOW=datetime(2026,10,30,4,0,tzinfo=timezone.utc)
SCOPE=TenantScope('org-org','dev-project')
RESERVATION_ID=UUID('11111111-1111-4111-8111-111111111111')
INVOCATION_ID=UUID('22222222-2222-4222-8222-222222222222')


def ref(kind,ident):
    return BudgetExactRef(resourceType=kind,resourceId=ident,revision=1,
        contentHash='sha256:'+hashlib.sha256((kind+ident).encode()).hexdigest())


def request(purpose='target'):
    call='route-call-'+purpose
    return ReserveBudgetRequest(operationId='aip_route_eval_'+purpose+'_call',
        invocationKey=call,taskRef=ref('Task','task'),
        policyRef=ref('BudgetRevision','budget'),
        pricingRef=ref('ModelPriceSnapshotRevision','price'),
        approvalRef=ref('ActionApprovalEvent','approval-'+purpose),
        currency='CNY',upperBoundMinor=100)


def command(purpose='target',input_bytes=b'input',*,target_call_key=None):
    value=request(purpose)
    invocation,reservation=AipBudgetReservationStore.initial_hold_refs(value,
        invocation_id=INVOCATION_ID if purpose=='target' else UUID('33333333-3333-4333-8333-333333333333'),
        reservation_id=RESERVATION_ID if purpose=='target' else UUID('44444444-4444-4444-8444-444444444444'))
    return RouteEvalExecutionCommand(tenant={'orgId':'org-org','projectId':'dev-project'},
        executionId='execution',manifestHash='a'*64,contextBindingHash='b'*64,
        admissionHash='c'*64,callKey=value.invocation_key,callBindingHash='d'*64,
        caseId='case',purpose=purpose,targetCallKey=target_call_key,
        budgetRequest=value,invocationRef=invocation,reservationRef=reservation,
        inputHash=hashlib.sha256(input_bytes).hexdigest(),executionAllowed=False)


def result(purpose='target',output_bytes=b'output'):
    return RouteEvalExecutionResult(tenant={'orgId':'org-org','projectId':'dev-project'},
        executionId='execution',callKey='route-call-'+purpose,caseId='case',purpose=purpose,
        providerRequestRef=ref('CapabilityProviderRequestReceipt','provider-request-'+purpose),
        providerResultId='provider-result-'+purpose,providerId='provider',modelId='model',
        outputHash=hashlib.sha256(output_bytes).hexdigest(),promptTokens=3,
        completionTokens=4,observedAt=NOW,executionAllowed=False)


class Rows:
    def __init__(self,one=None,many=None):self.one=one;self.many=many
    def fetchone(self):return self.one
    def fetchall(self):return self.many or []


class JournalConnection:
    def __init__(self):
        self.commands={};self.results={};self.sql=[]
        self.reservations={
            RESERVATION_ID:self._reservation('target',RESERVATION_ID,INVOCATION_ID),
            UUID('44444444-4444-4444-8444-444444444444'):
                self._reservation('judge',UUID('44444444-4444-4444-8444-444444444444'),
                    UUID('33333333-3333-4333-8333-333333333333')),
        }
    @staticmethod
    def _reservation(purpose,reservation_id,invocation_id):
        value=request(purpose)
        provider=result(purpose).provider_request_ref.model_dump(mode='json',by_alias=True)
        return {'org_id':'org-org','project_id':'dev-project','reservation_id':reservation_id,
            'invocation_id':invocation_id,'state':'held','operation_id':value.operation_id,
            'invocation_key':value.invocation_key,'request_hash':value.request_hash(),
            'approval_ref':value.approval_ref.model_dump(mode='json',by_alias=True),
            'provider_request_receipt_ref':provider}
    def execute(self,sql,params=()):
        text=' '.join(str(sql).split());self.sql.append(text)
        assert text.startswith(('SELECT ','INSERT '))
        if 'FROM public.aip_budget_reservation' in text:
            return Rows(self.reservations.get(params[-1]))
        if 'FROM public.aip_route_eval_execution_command' in text and 'JOIN' not in text:
            return Rows(self.commands.get(params[-1]))
        if 'FROM public.aip_route_eval_execution_result' in text and 'JOIN' not in text:
            return Rows(self.results.get(params[-1]))
        if 'JOIN public.aip_route_eval_execution_result' in text:
            target=next((row for row in self.commands.values()
                if row['execution_id']==params[2] and row['case_id']==params[3]
                and row['purpose']=='target'),None)
            stored=None if target is None else self.results.get(target['reservation_id'])
            return Rows(None if target is None or stored is None else {
                'call_key':target['call_key'],'output_bytes':stored['output_bytes'],
                'output_hash':stored['output_hash']})
        if text.startswith('INSERT INTO public.aip_route_eval_execution_command'):
            (org,project,reservation_id,execution_id,case_id,purpose,call_key,
             command_hash,command_payload,input_hash,input_bytes)=params
            self.commands[reservation_id]={'org_id':org,'project_id':project,
                'reservation_id':reservation_id,'execution_id':execution_id,'case_id':case_id,
                'purpose':purpose,'call_key':call_key,'command_hash':command_hash,
                'command_payload':json.loads(command_payload),'input_hash':input_hash,
                'input_bytes':bytes(input_bytes)}
            return Rows()
        if text.startswith('INSERT INTO public.aip_route_eval_execution_result'):
            (org,project,reservation_id,provider_ref,result_hash,result_payload,
             output_hash,output_bytes)=params
            self.results[reservation_id]={'org_id':org,'project_id':project,
                'reservation_id':reservation_id,'provider_request_ref':json.loads(provider_ref),
                'result_hash':result_hash,'result_payload':json.loads(result_payload),
                'output_hash':output_hash,'output_bytes':bytes(output_bytes)}
            return Rows()
        raise AssertionError('unexpected SQL: '+text)
    def commit(self):raise AssertionError('journal cannot commit')
    rollback=commit


def test_target_command_and_result_exact_replay_are_idempotent_and_effect_closed():
    conn=JournalConnection();journal=RouteEvalExecutionJournal();raw=b'input';out=b'output'
    target=command(input_bytes=raw)
    assert journal.enqueue(conn,SCOPE,RESERVATION_ID,command=target,input_bytes=raw)==target
    assert journal.enqueue(conn,SCOPE,RESERVATION_ID,command=target,input_bytes=raw)==target
    conn.reservations[RESERVATION_ID]['state']='submitted'
    target_result=result(output_bytes=out)
    assert journal.record_result(conn,SCOPE,RESERVATION_ID,
        result=target_result,output_bytes=out)==target_result
    assert journal.record_result(conn,SCOPE,RESERVATION_ID,
        result=target_result,output_bytes=out)==target_result
    read=journal.read(conn,SCOPE,RESERVATION_ID)
    assert read['command']==target and read['inputBytes']==raw
    assert read['result']==target_result and read['outputBytes']==out
    assert all(sql.startswith(('SELECT ','INSERT ')) for sql in conn.sql)


def test_judge_requires_same_case_target_result_raw_bytes_and_rejects_forged_hash():
    conn=JournalConnection();journal=RouteEvalExecutionJournal();target=command();out=b'output'
    journal.enqueue(conn,SCOPE,RESERVATION_ID,command=target,input_bytes=b'input')
    conn.reservations[RESERVATION_ID]['state']='submitted'
    journal.record_result(conn,SCOPE,RESERVATION_ID,result=result(output_bytes=out),output_bytes=out)
    judge_id=UUID('44444444-4444-4444-8444-444444444444')
    judge=command('judge',out,target_call_key=target.call_key)
    assert journal.enqueue(conn,SCOPE,judge_id,command=judge,input_bytes=out)==judge

    forged_conn=JournalConnection()
    journal.enqueue(forged_conn,SCOPE,RESERVATION_ID,command=target,input_bytes=b'input')
    forged_conn.reservations[RESERVATION_ID]['state']='submitted'
    journal.record_result(forged_conn,SCOPE,RESERVATION_ID,
        result=result(output_bytes=out),output_bytes=out)
    forged_bytes=bytearray(out);forged_bytes[0]^=1
    forged_bytes=bytes(forged_bytes)
    forged_hash=hashlib.sha256(forged_bytes).hexdigest()
    forged_conn.results[RESERVATION_ID]['output_hash']=forged_hash
    forged=command('judge',forged_bytes,target_call_key=target.call_key)
    with pytest.raises(RouteEvalExecutionConflict):
        journal.enqueue(forged_conn,SCOPE,judge_id,
            command=forged,input_bytes=forged_bytes)


@pytest.mark.parametrize('fault',['input','request','state','tenant','provider','result'])
def test_journal_rejects_command_or_result_authority_drift(fault):
    conn=JournalConnection();journal=RouteEvalExecutionJournal();target=command();raw=b'input'
    if fault=='input':
        with pytest.raises(RouteEvalExecutionConflict):
            journal.enqueue(conn,SCOPE,RESERVATION_ID,command=target,input_bytes=b'wrong')
        return
    if fault=='request':conn.reservations[RESERVATION_ID]['request_hash']='0'*64
    if fault=='state':conn.reservations[RESERVATION_ID]['state']='settled'
    if fault=='tenant':
        with pytest.raises((RouteEvalExecutionConflict,ValueError)):
            journal.enqueue(conn,TenantScope('dev-org','dev-project'),RESERVATION_ID,
                command=target,input_bytes=raw)
        return
    if fault in {'request','state'}:
        with pytest.raises(RouteEvalExecutionConflict):
            journal.enqueue(conn,SCOPE,RESERVATION_ID,command=target,input_bytes=raw)
        return
    journal.enqueue(conn,SCOPE,RESERVATION_ID,command=target,input_bytes=raw)
    conn.reservations[RESERVATION_ID]['state']='submitted'
    value=result()
    if fault=='provider':conn.reservations[RESERVATION_ID]['provider_request_receipt_ref']=ref(
        'CapabilityProviderRequestReceipt','other').model_dump(mode='json',by_alias=True)
    else:value=value.model_copy(update={'call_key':'other'})
    with pytest.raises(RouteEvalExecutionConflict):
        journal.record_result(conn,SCOPE,RESERVATION_ID,result=value,output_bytes=b'output')


def test_read_rejects_persistent_hash_or_raw_byte_drift():
    conn=JournalConnection();journal=RouteEvalExecutionJournal();target=command()
    journal.enqueue(conn,SCOPE,RESERVATION_ID,command=target,input_bytes=b'input')
    conn.commands[RESERVATION_ID]['input_bytes']=b'changed'
    with pytest.raises(RouteEvalExecutionConflict):journal.read(conn,SCOPE,RESERVATION_ID)

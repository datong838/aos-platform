// @vitest-environment jsdom
import { beforeEach, expect, it, vi } from 'vitest';
const state=vi.hoisted(()=>({tenant:{orgId:'org-org',projectId:'dev-project',subject:'operator'},auth:1}));
vi.mock('./tenant',()=>({getTenant:()=>state.tenant,getAuthRevision:()=>state.auth,tenantAuthHeaders:()=>({'X-Org-Id':state.tenant.orgId,'X-Project-Id':state.tenant.projectId,Authorization:'Bearer fixture'})}));
vi.mock('./apiBase',()=>({getApiBase:()=>'/api'}));
import { groupScope, listGroups, submitGroupCommand, pendingGroupCommand, confirmGroupCommand,readGroupRuntime } from './snapshotSchedules';
const definition='12345678-1234-4234-8234-123456789012';
const ref={resourceType:'SnapshotScheduleDefinitionRevision',resourceId:'snapshot-schedule-'+definition,revision:1,contentHash:'sha256:'+'a'.repeat(64)};
beforeEach(()=>{localStorage.clear();vi.restoreAllMocks();state.tenant={orgId:'org-org',projectId:'dev-project',subject:'operator'};state.auth=1;});

function runtimePayload(){return {orgId:'org-org',projectId:'dev-project',definitionId:definition,definitionRef:ref,configurationState:'enabled',executionAuthorized:false,routingStatus:'not_due',originalGroups:[],observedAt:'2026-09-16T09:30:00+00:00',worker:{state:'DISABLED',available:false,active:false,errorCode:null}};}
it('reads scoped exact runtime state without making a write',async()=>{
 const fetcher=vi.fn().mockResolvedValue(new Response(JSON.stringify(runtimePayload())));vi.stubGlobal('fetch',fetcher);
 const result=await readGroupRuntime(groupScope(),definition,ref);
 expect(result.worker.available).toBe(false);expect(fetcher.mock.calls[0][1].method).toBe('GET');
});
it('rejects drifted or inconsistent runtime projections',async()=>{
 for(const patch of [{orgId:'other'},{definitionRef:{...ref,revision:2}},{executionAuthorized:true},{worker:{state:'DISABLED',available:true,active:true,errorCode:null}}]){
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({...runtimePayload(),...patch}))));
  await expect(readGroupRuntime(groupScope(),definition,ref)).rejects.toThrow();
 }
});

it('persists unknown result and never automatically retries a write',async()=>{
 const fetcher=vi.fn().mockRejectedValue(new Error('network'));vi.stubGlobal('fetch',fetcher);
 const scope=groupScope();
 await expect(submitGroupCommand(scope,definition,'disable',{expectedRef:ref})).rejects.toThrow();
 const pending=pendingGroupCommand(scope);expect(pending?.definitionId).toBe(definition);
 expect(fetcher).toHaveBeenCalledTimes(1);
 await expect(submitGroupCommand(scope,definition,'disable',{expectedRef:ref})).rejects.toThrow(/待确认/);
 expect(fetcher).toHaveBeenCalledTimes(1);
 fetcher.mockResolvedValue(new Response(JSON.stringify({message:'not found'}),{status:404}));
 await expect(confirmGroupCommand(scope)).rejects.toThrow();
 expect(fetcher.mock.calls[1][1].method).toBe('GET');
 expect(pendingGroupCommand(scope)?.key).toBe(pending?.key);
});

it('fails before sending when pending storage is unavailable',async()=>{
 vi.spyOn(Storage.prototype,'setItem').mockImplementation(()=>{throw new Error('quota');});
 const fetcher=vi.fn();vi.stubGlobal('fetch',fetcher);
 await expect(submitGroupCommand(groupScope(),definition,'disable',{expectedRef:ref})).rejects.toThrow();
 expect(fetcher).not.toHaveBeenCalled();
});

it('discards a response after tenant/auth context changes',async()=>{
 let resolve!:(response:Response)=>void;
 vi.stubGlobal('fetch',vi.fn(()=>new Promise<Response>(done=>{resolve=done;})));
 const request=listGroups(groupScope());
 state.auth+=1;
 resolve(new Response(JSON.stringify({items:[],nextCursor:null}),{status:200}));
 await expect(request).rejects.toThrow(/身份|租户/);
});

it('does not expose one tenant pending command in another tenant',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockRejectedValue(new Error('network')));
 const scope=groupScope();await expect(submitGroupCommand(scope,definition,'disable',{expectedRef:ref})).rejects.toThrow();
 state.tenant={...state.tenant,orgId:'dev-org'};
 expect(pendingGroupCommand(groupScope())).toBeNull();
 expect(pendingGroupCommand(scope)).not.toBeNull();
});

function receiptForPending(scope:ReturnType<typeof groupScope>){
 const pending=pendingGroupCommand(scope)!;
 const binding={resourceType:'PipelineScheduleControlBinding',resourceId:'schedule-control-'+definition,revision:1,contentHash:'sha256:'+'b'.repeat(64)};
 const control={...binding,resourceType:'PipelineRuntimeControlRevision',resourceId:'pipeline-control-'+definition};
 const policy={...binding,resourceType:'SnapshotRelationshipPolicy',resourceId:'content/policies/relationships.json',revision:'1.0.0'};
 return {ref:{...ref,revision:2},body:{schemaVersion:'aos.snapshot-schedule-definition/v1',orgId:scope.orgId,projectId:scope.projectId,definitionId:definition,revision:2,priorRef:ref,installationId:definition,generation:definition,state:'disabled',cron:'0 8 * * *',timezone:'Asia/Shanghai',policyRef:policy,actor:scope.subject,executor:'runtime',createdAt:'2026-09-16T01:00:00+00:00',members:Array.from({length:12},(_,i)=>({scheduleId:'s'+i,pipelineId:'p'+i,bindingRef:binding,controlRef:control}))},idempotencyKey:pending.key,requestHash:'sha256:'+'c'.repeat(64),request:{orgId:scope.orgId,projectId:scope.projectId,definitionId:definition,actor:scope.subject,intent:'disable',expectedRef:ref,settings:null}};
}
it('confirms the exact original receipt before clearing a successful command',async()=>{
 const scope=groupScope();
 const fetcher=vi.fn().mockImplementation(async(_url,init)=>new Response(JSON.stringify(init.method==='GET'?receiptForPending(scope):{}),{status:200}));vi.stubGlobal('fetch',fetcher);
 const result=await submitGroupCommand(scope,definition,'disable',{expectedRef:ref});
 expect(result.body.state).toBe('disabled');expect(pendingGroupCommand(scope)).toBeNull();
 expect(fetcher.mock.calls.map(call=>call[1].method)).toEqual(['POST','GET']);
 const key=new Headers(fetcher.mock.calls[0][1].headers).get('Idempotency-Key');
 expect(fetcher.mock.calls[1][0]).toContain('/receipts/'+key);
});
it('keeps the pending record when a receipt belongs to a different request',async()=>{
 const scope=groupScope();vi.stubGlobal('fetch',vi.fn().mockImplementation(async(_url,init)=>{
 const receipt=init.method==='GET'?receiptForPending(scope):null;if(receipt)receipt.request.intent='enable';
 return new Response(JSON.stringify(receipt||{}),{status:200});}));
 await expect(submitGroupCommand(scope,definition,'disable',{expectedRef:ref})).rejects.toThrow(/不一致/);
 expect(pendingGroupCommand(scope)).not.toBeNull();
});

it('retains the original command when the bounded request times out',async()=>{
 vi.useFakeTimers();
 try{
  const fetcher=vi.fn((_url,init)=>new Promise((_resolve,reject)=>init.signal.addEventListener('abort',()=>reject(new Error('timeout')))));vi.stubGlobal('fetch',fetcher);
  const scope=groupScope();const result=submitGroupCommand(scope,definition,'disable',{expectedRef:ref});
  const assertion=expect(result).rejects.toThrow('timeout');await vi.advanceTimersByTimeAsync(30000);await assertion;
  expect(pendingGroupCommand(scope)).not.toBeNull();expect(fetcher).toHaveBeenCalledTimes(1);
 }finally{vi.useRealTimers();}
});

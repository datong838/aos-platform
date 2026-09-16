// @vitest-environment jsdom
import {beforeEach,expect,it,vi} from 'vitest';
const state=vi.hoisted(()=>({tenant:{orgId:'org-org',projectId:'dev-project',subject:'operator'},auth:1}));
vi.mock('./tenant',()=>({getTenant:()=>state.tenant,getAuthRevision:()=>state.auth,tenantAuthHeaders:()=>({'X-Org-Id':state.tenant.orgId,'X-Project-Id':state.tenant.projectId,Authorization:'Bearer fixture'})}));
vi.mock('./apiBase',()=>({getApiBase:()=>'/api'}));
import {groupScope,readRecoveryContext,submitRecoveryCommand,pendingRecoveryCommand,confirmRecoveryCommand,submitGroupCommand} from './snapshotSchedules';
const id='12345678-1234-4234-8234-123456789012',hash='sha256:'+'a'.repeat(64);
const definition={resourceType:'SnapshotScheduleDefinitionRevision',resourceId:'snapshot-schedule-'+id,revision:2,contentHash:hash};
function context(){return {status:'saved_input_verified',executionAuthorized:false,groupId:id,originalDefinitionRef:{...definition,revision:1},expectedDefinitionRef:definition,expectedRecoveryRef:null,inputManifestHash:hash,observation:{startedAt:'2026-09-15T00:00:00Z',completedAt:'2026-09-15T00:01:00Z'},windowRules:{maxDurationHours:24,notBeforeMinimum:'2026-09-15T00:00:00Z',expiresAfter:'2026-09-16T00:00:00Z',currentTime:'2026-09-16T09:00:00Z'},runStates:[{status:'running',executorStopped:false,finishedAt:null,count:12}]};}
const window={notBefore:'2026-09-16T09:00:00Z',expiresAt:'2026-09-16T10:00:00Z'};
beforeEach(()=>{localStorage.clear();vi.restoreAllMocks();state.tenant={orgId:'org-org',projectId:'dev-project',subject:'operator'};state.auth=1;});

async function readContext(){vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify(context()))));return readRecoveryContext(groupScope(),id,definition);}
it('retains original unknown renewal and confirms only by original key',async()=>{
 const original=await readContext(),scope=groupScope();
 const fetcher=vi.fn().mockRejectedValue(new Error('lost acknowledgement'));vi.stubGlobal('fetch',fetcher);
 await expect(submitRecoveryCommand(scope,original,window)).rejects.toThrow();
 const pending=pendingRecoveryCommand(scope)!;expect(pending.groupId).toBe(id);
 await expect(submitRecoveryCommand(scope,original,window)).rejects.toThrow(/待确认/);
 await expect(submitGroupCommand(scope,id,'disable',{expectedRef:definition})).rejects.toThrow(/待确认/);
 expect(fetcher).toHaveBeenCalledTimes(1);
 fetcher.mockResolvedValue(new Response(JSON.stringify({message:'missing'}),{status:404}));
 await expect(confirmRecoveryCommand(scope)).rejects.toThrow();
 expect(fetcher.mock.calls[1][0]).toContain('/receipts/'+pending.key);
 expect(fetcher.mock.calls[1][1].method).toBe('GET');expect(pendingRecoveryCommand(scope)?.key).toBe(pending.key);
});

function receipt(scope:ReturnType<typeof groupScope>){
 const p=pendingRecoveryCommand(scope)!;
 const request={schemaVersion:'aos.snapshot-group-recovery-request/v1',orgId:scope.orgId,projectId:scope.projectId,groupId:id,actor:scope.subject,...p.body};
 const r={resourceType:'SnapshotGroupRecoveryRevision',resourceId:'snapshot-recovery-'+id,revision:1,contentHash:hash};
 return {ref:r,idempotencyKey:p.key,requestHash:hash,request,body:{schemaVersion:'aos.snapshot-group-recovery/v1',mode:'saved-input-only',orgId:scope.orgId,projectId:scope.projectId,groupId:id,revision:1,priorRef:null,originalDefinitionRef:{...definition,revision:1},currentDefinitionRef:{...definition,revision:3},originalScheduleClaimHash:hash,originalSourceClaimHash:hash,inputManifestHash:hash,actor:scope.subject,executor:'original-runtime',policyRef:{resourceType:'SnapshotRelationshipPolicy',resourceId:'policy.json',revision:'1.0.0',contentHash:hash},requestHash:hash,createdAt:'2026-09-16T09:00:00Z'}};
}
it('validates original receipt before clearing pending renewal',async()=>{
 const original=await readContext(),scope=groupScope();
 const fetcher=vi.fn().mockImplementation(async(_url,init)=>new Response(JSON.stringify(init.method==='GET'?receipt(scope):{status:'approval_recorded',executionStarted:false})));vi.stubGlobal('fetch',fetcher);
 const result=await submitRecoveryCommand(scope,original,window);
 expect(result.body.currentDefinitionRef.revision).toBe(3);expect(pendingRecoveryCommand(scope)).toBeNull();
 expect(fetcher.mock.calls.map(c=>c[1].method)).toEqual(['POST','GET']);
});
it('keeps a mismatched receipt and prevents cross-tenant pending leakage',async()=>{
 const original=await readContext(),scope=groupScope();
 vi.stubGlobal('fetch',vi.fn().mockImplementation(async(_url,init)=>{if(init.method==='GET'){const saved=receipt(scope);saved.body.inputManifestHash='sha256:'+'b'.repeat(64);return new Response(JSON.stringify(saved));}return new Response('{}');}));
 await expect(submitRecoveryCommand(scope,original,window)).rejects.toThrow();expect(pendingRecoveryCommand(scope)).not.toBeNull();
 state.tenant={...state.tenant,orgId:'dev-org'};expect(pendingRecoveryCommand(groupScope())).toBeNull();
});
it('rejects a stale context or invalid window before writing',async()=>{
 const original=await readContext();const fetcher=vi.fn();vi.stubGlobal('fetch',fetcher);
 await expect(submitRecoveryCommand(groupScope(),original,{...window,expiresAt:'2026-09-18T10:00:00Z'})).rejects.toThrow();
 expect(fetcher).not.toHaveBeenCalled();
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({...context(),expectedDefinitionRef:{...definition,revision:9}}))));
 await expect(readRecoveryContext(groupScope(),id,definition)).rejects.toThrow();
});

it('does not send if durable pending storage fails',async()=>{
 const original=await readContext(),fetcher=vi.fn();vi.stubGlobal('fetch',fetcher);
 vi.spyOn(Storage.prototype,'setItem').mockImplementation(()=>{throw new Error('storage unavailable');});
 await expect(submitRecoveryCommand(groupScope(),original,window)).rejects.toThrow('storage unavailable');
 expect(fetcher).not.toHaveBeenCalled();
});
it('clears only a definitively rejected original renewal',async()=>{
 const original=await readContext(),scope=groupScope();
 const fetcher=vi.fn().mockResolvedValue(new Response(JSON.stringify({message:'current revision changed'}),{status:412}));vi.stubGlobal('fetch',fetcher);
 await expect(submitRecoveryCommand(scope,original,window)).rejects.toThrow('current revision changed');
 expect(pendingRecoveryCommand(scope)).toBeNull();expect(fetcher).toHaveBeenCalledTimes(1);
});
it('does not clear old pending after authentication changes during confirmation',async()=>{
 const original=await readContext(),scope=groupScope();
 vi.stubGlobal('fetch',vi.fn().mockRejectedValue(new Error('unknown')));
 await expect(submitRecoveryCommand(scope,original,window)).rejects.toThrow();
 let finish!:(r:Response)=>void;const body=receipt(scope);
 vi.stubGlobal('fetch',vi.fn(()=>new Promise<Response>(resolve=>{finish=resolve;})));
 const promise=confirmRecoveryCommand(scope);state.auth++;
 finish(new Response(JSON.stringify(body)));await expect(promise).rejects.toThrow(/身份|租户/);
 expect(pendingRecoveryCommand(scope)).not.toBeNull();
});

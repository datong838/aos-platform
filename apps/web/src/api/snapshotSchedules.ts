import { getAuthRevision, getTenant, tenantAuthHeaders } from './tenant';
import { getApiBase } from './apiBase';
export type GroupScope={orgId:string;projectId:string;subject:string;auth:number};
export type ExactRef={resourceType:string;resourceId:string;revision:number|string;contentHash:string};
export type GroupMember={scheduleId:string;pipelineId:string;bindingRef:ExactRef;controlRef:ExactRef;definitionId?:string|null};
export type GroupDefinition={ref:ExactRef;body:{schemaVersion:string;orgId:string;projectId:string;definitionId:string;revision:number;priorRef:ExactRef|null;installationId:string;generation:string;state:'disabled'|'enabled'|'retired';cron:string;timezone:string;policyRef:ExactRef;members:GroupMember[];actor:string;executor:string;createdAt:string}};
export type GroupOptions={installationId:string;generation:string;status:'ready'|'incomplete'|'policy_unavailable';missing:string[];ambiguous:string[];members:GroupMember[];policies:ExactRef[]};
export type GroupRuntime={orgId:string;projectId:string;definitionId:string;definitionRef:ExactRef;configurationState:GroupDefinition['body']['state'];executionAuthorized:false;routingStatus:string;originalGroups:{groupId:string;recoveryRef:ExactRef|null}[];observedAt:string;worker:{state:string;available:boolean;active:boolean;errorCode:string|null}};
export type GroupIntent='configure'|'enable'|'disable'|'retire';
export type GroupCommandBody={expectedRef:ExactRef|null;cron?:string;policyRef?:ExactRef;members?:{scheduleId:string;bindingRef:ExactRef}[]};
export type PendingGroupCommand={schema:1;scope:Omit<GroupScope,'auth'>;definitionId:string;key:string;intent:GroupIntent;body:GroupCommandBody};
const BASE='/v1/pipelines/snapshot-schedules', UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/, HASH=/^sha256:[0-9a-f]{64}$/;
const active=new Set<string>();
const object=(v:unknown):Record<string,unknown>=>{if(!v||typeof v!=='object'||Array.isArray(v))throw new Error('数据组返回格式无效');return v as Record<string,unknown>;};
const text=(v:unknown):string=>{if(typeof v!=='string'||!v||v.trim()!==v)throw new Error('数据组字段无效');return v;};
const uuid=(v:unknown):string=>{const s=text(v);if(!UUID.test(s))throw new Error('数据组标识无效');return s;};
function stable(v:unknown):unknown {if(Array.isArray(v))return v.map(stable);if(v&&typeof v==='object')return Object.fromEntries(Object.entries(v).sort(([a],[b])=>a.localeCompare(b)).map(([k,x])=>[k,stable(x)]));return v;}
const same=(a:unknown,b:unknown)=>JSON.stringify(stable(a))===JSON.stringify(stable(b));
function ref(v:unknown,kind?:string):ExactRef {const r=object(v);const x={resourceType:text(r.resourceType),resourceId:text(r.resourceId),revision:r.revision as number|string,contentHash:text(r.contentHash)};if(!HASH.test(x.contentHash)||(kind&&x.resourceType!==kind)||!(typeof x.revision==='string'&&x.revision.length>0||Number.isSafeInteger(x.revision)&&Number(x.revision)>0))throw new Error('精确引用无效');return x;}
function member(v:unknown):GroupMember {const m=object(v);return {scheduleId:text(m.scheduleId),pipelineId:text(m.pipelineId),bindingRef:ref(m.bindingRef,'PipelineScheduleControlBinding'),controlRef:ref(m.controlRef,'PipelineRuntimeControlRevision'),...(m.definitionId===undefined?{}:{definitionId:m.definitionId===null?null:uuid(m.definitionId)})};}
function array(v:unknown):unknown[]{if(!Array.isArray(v))throw new Error('数据组列表无效');return v;}
export function groupScope():GroupScope {const t=getTenant();return {orgId:text(t.orgId),projectId:text(t.projectId),subject:text(t.subject),auth:getAuthRevision()};}
function assertScope(scope:GroupScope){if(!same(groupScope(),scope))throw new Error('租户或登录身份已变化，请重新加载');}
export function parseGroup(value:unknown,scope:GroupScope):GroupDefinition {
 const root=object(value),b=object(root.body),r=ref(root.ref,'SnapshotScheduleDefinitionRevision'),id=uuid(b.definitionId);
 if(b.orgId!==scope.orgId||b.projectId!==scope.projectId||b.schemaVersion!=='aos.snapshot-schedule-definition/v1'||r.resourceId!=='snapshot-schedule-'+id||r.revision!==b.revision||!Number.isSafeInteger(b.revision)||Number(b.revision)<1||!['disabled','enabled','retired'].includes(String(b.state))||b.timezone!=='Asia/Shanghai')throw new Error('数据组租户、状态或版本不一致');
 const members=array(b.members).map(member);if(members.length!==12||new Set(members.map(m=>m.scheduleId)).size!==12)throw new Error('数据组必须包含十二个不同来源');
 const createdAt=text(b.createdAt);if(!/(Z|[+-]\d\d:\d\d)$/.test(createdAt)||!Number.isFinite(Date.parse(createdAt)))throw new Error('数据组时间无效');
 return {ref:r,body:{schemaVersion:String(b.schemaVersion),orgId:scope.orgId,projectId:scope.projectId,definitionId:id,revision:Number(b.revision),priorRef:b.priorRef===null?null:ref(b.priorRef,'SnapshotScheduleDefinitionRevision'),installationId:uuid(b.installationId),generation:uuid(b.generation),state:b.state as GroupDefinition['body']['state'],cron:text(b.cron),timezone:'Asia/Shanghai',policyRef:ref(b.policyRef,'SnapshotRelationshipPolicy'),members,actor:text(b.actor),executor:text(b.executor),createdAt}};
}
async function request(scope:GroupScope,path:string,method='GET',body?:unknown,key?:string,base=BASE):Promise<unknown>{
 assertScope(scope);const headers=new Headers(tenantAuthHeaders());headers.set('Content-Type','application/json');if(key)headers.set('Idempotency-Key',key);
 const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),30000);
 try{const response=await fetch(getApiBase().replace(/\/$/,'')+base+path,{method,headers,cache:'no-store',signal:controller.signal,...(body===undefined?{}:{body:JSON.stringify(body)})});
 assertScope(scope);const payload:unknown=await response.json();assertScope(scope);
 if(!response.ok)throw Object.assign(new Error(typeof object(payload).message==='string'?String(object(payload).message):'数据组操作未完成'),{status:response.status});return payload;
 }finally{clearTimeout(timeout);}
}
export async function listGroups(scope:GroupScope,after?:string){const p=object(await request(scope,'/definitions'+(after?'?after='+encodeURIComponent(uuid(after)):'')));const items=array(p.items).map(v=>parseGroup(v,scope));if(items.length>50||new Set(items.map(i=>i.body.definitionId)).size!==items.length)throw new Error('数据组分页无效');return {items,nextCursor:p.nextCursor===null?null:uuid(p.nextCursor)};}
export async function groupOptions(scope:GroupScope,installationId:string,generation:string):Promise<GroupOptions>{
 const p=object(await request(scope,'/options?'+new URLSearchParams({installationId:uuid(installationId),generation:uuid(generation)})));
 if(p.installationId!==installationId||p.generation!==generation||!['ready','incomplete','policy_unavailable'].includes(String(p.status)))throw new Error('数据组选项安装范围不一致');
 const result={installationId,generation,status:p.status as GroupOptions['status'],missing:array(p.missing).map(text),ambiguous:array(p.ambiguous).map(text),members:array(p.members).map(member),policies:array(p.policies).map(v=>ref(v,'SnapshotRelationshipPolicy'))};
 if(result.status==='ready'&&(result.members.length!==12||new Set(result.members.map(m=>m.scheduleId)).size!==12||!result.policies.length||result.missing.length||result.ambiguous.length))throw new Error('数据组选项并未完整就绪');return result;
}
function scopeIdentity(s:GroupScope){return {orgId:s.orgId,projectId:s.projectId,subject:s.subject};}
function storageKey(s:GroupScope){return 'aos-snapshot-schedule-pending-v1:'+JSON.stringify(scopeIdentity(s));}
export function pendingGroupCommand(scope:GroupScope):PendingGroupCommand|null {
 const raw=localStorage.getItem(storageKey(scope));if(raw===null)return null;
 const p=object(JSON.parse(raw));if(p.schema!==1||!same(p.scope,scopeIdentity(scope))||!['configure','enable','disable','retire'].includes(String(p.intent)))throw new Error('待确认记录格式异常，请保留记录核对');
 uuid(p.definitionId);text(p.key);object(p.body);return p as unknown as PendingGroupCommand;
}
export async function submitGroupCommand(scope:GroupScope,definitionId:string,intent:GroupIntent,body:GroupCommandBody):Promise<GroupDefinition>{
 assertScope(scope);uuid(definitionId);const lock=storageKey(scope);
 if(active.has(lock)||pendingGroupCommand(scope)||pendingRecoveryCommand(scope))throw new Error('存在待确认操作，请先核对原回执');active.add(lock);
 try {
  const pending:PendingGroupCommand={schema:1,scope:scopeIdentity(scope),definitionId,key:'snapshot-'+crypto.randomUUID(),intent,body:JSON.parse(JSON.stringify(body))};
  localStorage.setItem(lock,JSON.stringify(pending));
  try {await request(scope,'/'+definitionId+(intent==='configure'?'':'/'+intent),intent==='configure'?'PUT':'POST',pending.body,pending.key);}
  catch(error){const status=(error as {status?:number}).status;if(status&&status>=400&&status<500&&pendingGroupCommand(scope)?.key===pending.key)localStorage.removeItem(lock);throw error;}
  return await confirmGroupCommand(scope);
 } finally {active.delete(lock);}
}
export async function confirmGroupCommand(scope:GroupScope):Promise<GroupDefinition>{
 assertScope(scope);const pending=pendingGroupCommand(scope);if(!pending)throw new Error('没有待确认操作');
 const payload=object(await request(scope,'/'+uuid(pending.definitionId)+'/receipts/'+encodeURIComponent(pending.key)));
 const result=parseGroup(payload,scope),r=object(payload.request),settings=r.settings===null?null:object(r.settings);
 const expectedState={configure:'disabled',enable:'enabled',disable:'disabled',retire:'retired'}[pending.intent];
 if(result.body.state!==expectedState||!same(result.body.priorRef,pending.body.expectedRef)||result.body.revision!==(pending.body.expectedRef?Number(pending.body.expectedRef.revision)+1:1))throw new Error('原回执状态与前驱不一致');
 if(payload.idempotencyKey!==pending.key||!HASH.test(text(payload.requestHash))||result.body.definitionId!==pending.definitionId||result.body.actor!==scope.subject||r.orgId!==scope.orgId||r.projectId!==scope.projectId||r.actor!==scope.subject||r.definitionId!==pending.definitionId||r.intent!==pending.intent||!same(r.expectedRef,pending.body.expectedRef))throw new Error('原回执与待确认请求不一致，请保留原记录');
 if(pending.intent==='configure'){
  if(!settings||settings.cron!==pending.body.cron||!same(settings.policyRef,pending.body.policyRef))throw new Error('原配置回执参数不一致');
  const simplify=(items:unknown[])=>items.map(v=>{const m=object(v);return {scheduleId:text(m.scheduleId),bindingRef:ref(m.bindingRef,'PipelineScheduleControlBinding')};}).sort((a,b)=>a.scheduleId.localeCompare(b.scheduleId));
  if(!same(simplify(array(settings.members)),simplify(array(pending.body.members))))throw new Error('原配置回执成员不一致');
 } else if(settings!==null)throw new Error('原状态回执参数不一致');
 assertScope(scope);if(pendingGroupCommand(scope)?.key!==pending.key)throw new Error('待确认命令已变化');localStorage.removeItem(storageKey(scope));return result;
}

export async function readGroup(scope:GroupScope,definitionId:string){return parseGroup(await request(scope,"/"+uuid(definitionId)),scope);}

export async function readGroupRuntime(scope:GroupScope,definitionId:string,expectedRef:ExactRef):Promise<GroupRuntime>{
 const value=object(await request(scope,'/'+uuid(definitionId)+'/runtime')),worker=object(value.worker);
 const exact=ref(value.definitionRef,'SnapshotScheduleDefinitionRevision');
 if(value.orgId!==scope.orgId||value.projectId!==scope.projectId||value.definitionId!==definitionId||exact.resourceId!=='snapshot-schedule-'+definitionId||!same(exact,expectedRef))throw new Error('运行状态的租户或配置版本已变化，请刷新配置');
 if(value.executionAuthorized!==false||!['disabled','enabled','retired'].includes(String(value.configurationState))||!['disabled','retired','due','not_due','original_group_pending','slot_completed','recovery_only'].includes(String(value.routingStatus)))throw new Error('运行状态格式无效');
 if(!['DISABLED','FAILED_CLOSED','STOPPED','NOT_SELECTED','UNAVAILABLE','RUNNING','IDLE','STOPPING'].includes(String(worker.state))||typeof worker.available!=='boolean'||typeof worker.active!=='boolean'||worker.available&&!['RUNNING','IDLE'].includes(String(worker.state))||worker.active&&(!worker.available||worker.state!=='RUNNING')||worker.errorCode!==null&&worker.errorCode!=='SNAPSHOT_TICK_UNCONFIRMED')throw new Error('执行器状态不一致');
 const observedAt=text(value.observedAt);if(!/(Z|[+-]\d\d:\d\d)$/.test(observedAt)||!Number.isFinite(Date.parse(observedAt)))throw new Error('运行状态时间无效');
 const groups=array(value.originalGroups).map(item=>{const group=object(item),groupId=uuid(group.groupId),recoveryRef=group.recoveryRef===null?null:ref(group.recoveryRef,'SnapshotGroupRecoveryRevision');if(recoveryRef&&recoveryRef.resourceId!=='snapshot-recovery-'+groupId)throw new Error('恢复回执范围不一致');return {groupId,recoveryRef};});
 if(new Set(groups.map(g=>g.groupId)).size!==groups.length)throw new Error('原任务标识重复');
 return {orgId:scope.orgId,projectId:scope.projectId,definitionId,definitionRef:exact,configurationState:value.configurationState as GroupRuntime['configurationState'],executionAuthorized:false,routingStatus:String(value.routingStatus),originalGroups:groups,observedAt,worker:{state:String(worker.state),available:worker.available,active:worker.active,errorCode:worker.errorCode as string|null}};
}

export type RecoveryContext={scope:Omit<GroupScope,'auth'>;groupId:string;originalDefinitionRef:ExactRef;expectedDefinitionRef:ExactRef;expectedRecoveryRef:ExactRef|null;inputManifestHash:string;observation:{startedAt:string;completedAt:string};windowRules:{maxDurationHours:24;notBeforeMinimum:string;expiresAfter:string;currentTime:string};runStates:{status:string;executorStopped:boolean|null;finishedAt:string|null;count:number}[]};
export type RecoveryWindow={notBefore:string;expiresAt:string};
export type RecoveryBody=RecoveryWindow&{expectedDefinitionRef:ExactRef;expectedRecoveryRef:ExactRef|null;inputManifestHash:string};
export type PendingRecoveryCommand={schema:1;scope:Omit<GroupScope,'auth'>;groupId:string;key:string;body:RecoveryBody};
export type RecoveryReceipt={ref:ExactRef;body:{groupId:string;currentDefinitionRef:ExactRef;inputManifestHash:string}};
const RECOVERY_BASE='/v1/pipelines/snapshot-recoveries';
function aware(value:unknown){const result=text(value);if(!/(Z|[+-]\d\d:\d\d)$/.test(result)||!Number.isFinite(Date.parse(result)))throw new Error('恢复时间必须包含时区');return result;}
function hash(value:unknown){const result=text(value);if(!HASH.test(result))throw new Error('恢复输入标识无效');return result;}
function recoveryRef(value:unknown,groupId:string){if(value===null)return null;const result=ref(value,'SnapshotGroupRecoveryRevision');if(result.resourceId!=='snapshot-recovery-'+groupId||!Number.isSafeInteger(result.revision)||Number(result.revision)<1)throw new Error('恢复回执范围无效');return result;}
function definitionRef(value:unknown){const result=ref(value,'SnapshotScheduleDefinitionRevision');uuid(result.resourceId.replace(/^snapshot-schedule-/,''));if(!result.resourceId.startsWith('snapshot-schedule-')||!Number.isSafeInteger(result.revision))throw new Error('恢复配置引用无效');return result;}
function recoveryBody(value:unknown,groupId:string):RecoveryBody{const v=object(value);return {expectedDefinitionRef:definitionRef(v.expectedDefinitionRef),expectedRecoveryRef:recoveryRef(v.expectedRecoveryRef,groupId),inputManifestHash:hash(v.inputManifestHash),notBefore:aware(v.notBefore),expiresAt:aware(v.expiresAt)};}
export async function readRecoveryContext(scope:GroupScope,groupId:string,expectedRef:ExactRef):Promise<RecoveryContext>{
 const v=object(await request(scope,'/'+uuid(groupId),'GET',undefined,undefined,RECOVERY_BASE));
 const original=definitionRef(v.originalDefinitionRef),current=definitionRef(v.expectedDefinitionRef),observation=object(v.observation),rules=object(v.windowRules);
 if(v.status!=='saved_input_verified'||v.executionAuthorized!==false||v.groupId!==groupId||!same(current,expectedRef)||original.resourceId!==current.resourceId||Number(original.revision)>Number(current.revision)||rules.maxDurationHours!==24)throw new Error('原任务或当前配置已变化，请重新核对');
 const startedAt=aware(observation.startedAt),completedAt=aware(observation.completedAt);if(Date.parse(startedAt)>Date.parse(completedAt))throw new Error('原采集时间顺序无效');
 const runStates=array(v.runStates).map(item=>{const r=object(item);if(!Number.isSafeInteger(r.count)||Number(r.count)<1||!(r.executorStopped===null||typeof r.executorStopped==='boolean'))throw new Error('原运行状态无效');return {status:text(r.status),executorStopped:r.executorStopped as boolean|null,finishedAt:r.finishedAt===null?null:aware(r.finishedAt),count:Number(r.count)};});
 if(runStates.reduce((sum,r)=>sum+r.count,0)!==12)throw new Error('原任务必须包含十二个运行记录');
 return {scope:scopeIdentity(scope),groupId,originalDefinitionRef:original,expectedDefinitionRef:current,expectedRecoveryRef:recoveryRef(v.expectedRecoveryRef,groupId),inputManifestHash:hash(v.inputManifestHash),observation:{startedAt,completedAt},windowRules:{maxDurationHours:24,notBeforeMinimum:aware(rules.notBeforeMinimum),expiresAfter:aware(rules.expiresAfter),currentTime:aware(rules.currentTime)},runStates};
}
function recoveryStorageKey(scope:GroupScope){return 'aos-snapshot-recovery-pending-v1:'+JSON.stringify(scopeIdentity(scope));}
function recoveryChanged(){window.dispatchEvent(new Event('aos-snapshot-recovery-updated'));}
export function pendingRecoveryCommand(scope:GroupScope):PendingRecoveryCommand|null{
 const raw=localStorage.getItem(recoveryStorageKey(scope));if(raw===null)return null;
 const value=object(JSON.parse(raw)),groupId=uuid(value.groupId);
 if(value.schema!==1||!same(value.scope,scopeIdentity(scope)))throw new Error('待确认恢复记录异常，请保留核对');
 return {schema:1,scope:scopeIdentity(scope),groupId,key:text(value.key),body:recoveryBody(value.body,groupId)};
}
export async function submitRecoveryCommand(scope:GroupScope,context:RecoveryContext,window:RecoveryWindow):Promise<RecoveryReceipt>{
 assertScope(scope);if(!same(context.scope,scopeIdentity(scope)))throw new Error('恢复上下文属于其他登录范围');
 const groupId=uuid(context.groupId),lock=recoveryStorageKey(scope);
 if(active.has(lock)||pendingRecoveryCommand(scope)||pendingGroupCommand(scope))throw new Error('存在待确认操作，请先核对原回执');
 const body=recoveryBody({...window,expectedDefinitionRef:context.expectedDefinitionRef,expectedRecoveryRef:context.expectedRecoveryRef,inputManifestHash:context.inputManifestHash},groupId);
 const start=Date.parse(body.notBefore),end=Date.parse(body.expiresAt),now=Date.parse(context.windowRules.currentTime);
 if(!(end>start&&end-start<=86400000&&start>=Date.parse(context.windowRules.notBeforeMinimum)&&end>Date.parse(context.windowRules.expiresAfter)&&start<=now&&end>now))throw new Error('恢复窗口不满足当前规则，请重新核对');
 const running=context.runStates.every(r=>r.status==='running'&&r.executorStopped!==true&&r.finishedAt===null),failed=context.runStates.every(r=>r.status==='failed'&&r.executorStopped===true&&r.finishedAt!==null);
 if(!running&&!failed)throw new Error('原任务状态尚不能办理恢复');
 active.add(lock);
 try{
  const pending:PendingRecoveryCommand={schema:1,scope:scopeIdentity(scope),groupId,key:'snapshot-recovery-'+crypto.randomUUID(),body};
  localStorage.setItem(lock,JSON.stringify(pending));recoveryChanged();
  try{await request(scope,'/'+groupId+'/renew','POST',body,pending.key,RECOVERY_BASE);}
  catch(error){const status=(error as {status?:number}).status;if(status&&status>=400&&status<500&&pendingRecoveryCommand(scope)?.key===pending.key){localStorage.removeItem(lock);recoveryChanged();}throw error;}
  return await confirmRecoveryCommand(scope);
 }finally{active.delete(lock);}
}
export async function confirmRecoveryCommand(scope:GroupScope):Promise<RecoveryReceipt>{
 assertScope(scope);const pending=pendingRecoveryCommand(scope);if(!pending)throw new Error('没有待确认恢复操作');
 const value=object(await request(scope,'/'+pending.groupId+'/receipts/'+encodeURIComponent(pending.key),'GET',undefined,undefined,RECOVERY_BASE)),body=object(value.body),r=object(value.request);
 const exact=recoveryRef(value.ref,pending.groupId),current=definitionRef(body.currentDefinitionRef),original=definitionRef(body.originalDefinitionRef);
 const expectedRevision=pending.body.expectedRecoveryRef?Number(pending.body.expectedRecoveryRef.revision)+1:1;
 if(!exact||exact.revision!==expectedRevision||body.revision!==expectedRevision||body.schemaVersion!=='aos.snapshot-group-recovery/v1'||body.mode!=='saved-input-only'||body.orgId!==scope.orgId||body.projectId!==scope.projectId||body.groupId!==pending.groupId||body.actor!==scope.subject||!same(body.priorRef,pending.body.expectedRecoveryRef)||body.inputManifestHash!==pending.body.inputManifestHash||current.resourceId!==pending.body.expectedDefinitionRef.resourceId||current.revision!==Number(pending.body.expectedDefinitionRef.revision)+1||original.resourceId!==current.resourceId||Number(original.revision)>Number(pending.body.expectedDefinitionRef.revision))throw new Error('恢复回执与原请求不一致，请保留记录');
 if(value.idempotencyKey!==pending.key||hash(value.requestHash)!==body.requestHash||r.schemaVersion!=='aos.snapshot-group-recovery-request/v1'||r.orgId!==scope.orgId||r.projectId!==scope.projectId||r.groupId!==pending.groupId||r.actor!==scope.subject||!same(r.expectedDefinitionRef,pending.body.expectedDefinitionRef)||!same(r.expectedRecoveryRef,pending.body.expectedRecoveryRef)||r.inputManifestHash!==pending.body.inputManifestHash||Date.parse(aware(r.notBefore))!==Date.parse(pending.body.notBefore)||Date.parse(aware(r.expiresAt))!==Date.parse(pending.body.expiresAt))throw new Error('恢复原回执参数不一致，请保留记录');
 hash(body.originalScheduleClaimHash);hash(body.originalSourceClaimHash);text(body.executor);ref(body.policyRef,'SnapshotRelationshipPolicy');aware(body.createdAt);
 assertScope(scope);if(pendingRecoveryCommand(scope)?.key!==pending.key)throw new Error('待确认恢复记录已变化');localStorage.removeItem(recoveryStorageKey(scope));recoveryChanged();
 return {ref:exact,body:{groupId:pending.groupId,currentDefinitionRef:current,inputManifestHash:pending.body.inputManifestHash}};
}

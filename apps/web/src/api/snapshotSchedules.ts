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
async function request(scope:GroupScope,path:string,method='GET',body?:unknown,key?:string):Promise<unknown>{
 assertScope(scope);const headers=new Headers(tenantAuthHeaders());headers.set('Content-Type','application/json');if(key)headers.set('Idempotency-Key',key);
 const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),30000);
 try{const response=await fetch(getApiBase().replace(/\/$/,'')+BASE+path,{method,headers,cache:'no-store',signal:controller.signal,...(body===undefined?{}:{body:JSON.stringify(body)})});
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
 if(active.has(lock)||pendingGroupCommand(scope))throw new Error('存在待确认操作，请先核对原回执');active.add(lock);
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

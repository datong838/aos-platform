import { useCallback,useEffect,useRef,useState } from 'react';
import { assetControlClient } from '../../api/assetControl/client';
import type { InstallationListItem } from '../../api/assetControl/types';
import { confirmGroupCommand,confirmRecoveryCommand,groupOptions,groupScope,listGroups,readGroup,readGroupRuntime,pendingGroupCommand,pendingRecoveryCommand,submitGroupCommand,type GroupDefinition,type GroupIntent,type GroupOptions,type GroupScope,type GroupRuntime,type PendingGroupCommand,type PendingRecoveryCommand,type RecoveryReceipt } from '../../api/snapshotSchedules';
import {SnapshotRecoveryPanel} from './SnapshotRecoveryPanel';
import { getPipelineDisplayName } from './pipelineMeta';
import './SnapshotSchedulesPanel.css';

const labels={disabled:'已配置 · 已停用',enabled:'已启用配置',retired:'已退役'};
function scopeOrNull(){try{return groupScope();}catch{return null;}}
function RuntimeStatus({scope,group,blocked,onConfirmed,onBusy}:{scope:GroupScope;group:GroupDefinition;blocked:boolean;onConfirmed:(receipt:RecoveryReceipt)=>Promise<void>;onBusy:(busy:boolean)=>void}){
 const [value,setValue]=useState<GroupRuntime|null>(null),[error,setError]=useState<string|null>(null),[loading,setLoading]=useState(false);
 const mounted=useRef(false),epoch=useRef(0);
 const refresh=useCallback(async()=>{
  const sequence=++epoch.current;setLoading(true);setError(null);setValue(null);
  const current=()=>mounted.current&&sequence===epoch.current&&JSON.stringify(scopeOrNull())===JSON.stringify(scope);
  try{const result=await readGroupRuntime(scope,group.body.definitionId,group.ref);if(current())setValue(result);}
  catch(e){if(current())setError((e as Error).message);}
  finally{if(current())setLoading(false);}
 },[scope,group]);
 useEffect(()=>{mounted.current=true;void refresh();return()=>{mounted.current=false;epoch.current+=1;};},[refresh]);
 let label='正在核对运行情况';
 if(value){
  if(value.configurationState==='disabled')label='数据组已停用';
  else if(value.configurationState==='retired')label='数据组已退役';
  else if(value.worker.active)label='正在执行当前数据组';
  else if(!value.worker.available)label=value.worker.state==='DISABLED'?'执行器尚未启用':value.worker.state==='STOPPING'?'执行器正在停止':'执行器当前不可用';
  else if(value.worker.errorCode)label='执行结果待核对';
  else if(value.routingStatus==='original_group_pending')label=value.originalGroups.length>0&&value.originalGroups.every(g=>g.recoveryRef)?'原任务恢复已批准，等待执行器承接':'原任务尚未完成，需核对恢复条件';
  else if(value.routingStatus==='recovery_only')label='原任务恢复已结束，后续采集需重新配置';
  else if(value.routingStatus==='slot_completed')label='本周期任务已完成';
  else label='执行器已就绪，等待采集周期';
 }
 return <aside className="snapshot-groups__notice" aria-label="数据组运行状态"><h4>当前运行情况</h4>{error?<p role="alert">运行状态尚未确认：{error}</p>:<p role="status">{label}</p>}<div className="snapshot-groups__header">{value&&<small>核对时间：{new Date(value.observedAt).toLocaleString('zh-CN')}</small>}<button type="button" disabled={loading||blocked} onClick={()=>void refresh()}>刷新运行状态</button></div>{value?.routingStatus==='original_group_pending'&&value.originalGroups.length===1&&<SnapshotRecoveryPanel key={value.originalGroups[0].groupId} scope={scope} groupId={value.originalGroups[0].groupId} definitionRef={group.ref} blocked={blocked||value.worker.active} onConfirmed={onConfirmed} onBusy={onBusy}/>}</aside>;
}
export function SnapshotSchedulesPanel(){
 const [scope,setScope]=useState(scopeOrNull);
 useEffect(()=>{const change=()=>setScope(scopeOrNull());window.addEventListener('aos-tenant-updated',change);window.addEventListener('aos-auth-updated',change);return()=>{window.removeEventListener('aos-tenant-updated',change);window.removeEventListener('aos-auth-updated',change);};},[]);
 return scope?<GroupPanel key={JSON.stringify(scope)} scope={scope}/>:<p role="status">请先确认当前登录身份，再配置整组采集。</p>;
}
function GroupPanel({scope}:{scope:GroupScope}){
 const [groups,setGroups]=useState<GroupDefinition[]>([]),[next,setNext]=useState<string|null>(null);
 const [installations,setInstallations]=useState<InstallationListItem[]>([]),[installationTotal,setInstallationTotal]=useState(0);
 const [installation,setInstallation]=useState(''),[selected,setSelected]=useState<GroupDefinition|null>(null);
 const [options,setOptions]=useState<GroupOptions|null>(null),[policy,setPolicy]=useState(''),[cron,setCron]=useState('0 8 * * *');
 const [error,setError]=useState<string|null>(null),[message,setMessage]=useState<string|null>(null),[busy,setBusy]=useState(false);
 const [pending,setPending]=useState<PendingGroupCommand|null>(null),[pendingError,setPendingError]=useState(false);
 const [recoveryPending,setRecoveryPending]=useState<PendingRecoveryCommand|null>(null);
 const [confirmRetire,setConfirmRetire]=useState(false);
 const lock=useRef(false),mounted=useRef(true),selectionEpoch=useRef(0);
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;selectionEpoch.current+=1;};},[]);
 const current=()=>mounted.current&&JSON.stringify(scopeOrNull())===JSON.stringify(scope);
 const syncPending=useCallback(()=>{try{setPending(pendingGroupCommand(scope));setRecoveryPending(pendingRecoveryCommand(scope));setPendingError(false);}catch(e){setPendingError(true);setError((e as Error).message);}},[scope]);
 useEffect(()=>{window.addEventListener('aos-snapshot-recovery-updated',syncPending);return()=>window.removeEventListener('aos-snapshot-recovery-updated',syncPending);},[syncPending]);
 const reload=useCallback(async()=>{const page=await listGroups(scope);if(!mounted.current)return;setGroups(page.items);setNext(page.nextCursor);},[scope]);
 useEffect(()=>{syncPending();void reload().catch(e=>{if(mounted.current)setError(e.message);});void assetControlClient.listInstallations({state:'active',limit:50}).then(page=>{if(current()){setInstallations(page.items);setInstallationTotal(page.total);}}).catch(e=>{if(current())setError(e.message);});},[reload,scope,syncPending]);
 const locked=busy||!!pending||!!recoveryPending||pendingError;
 async function recovered(receipt:RecoveryReceipt){
  if(!current())return;setMessage('原恢复申请回执已核对，等待执行器按当前条件承接。');syncPending();
  const id=receipt.body.currentDefinitionRef.resourceId.replace(/^snapshot-schedule-/,'');
  const latest=await readGroup(scope,id);if(!current())return;setSelected(latest);setInstallation(latest.body.installationId);setCron(latest.body.cron);await reload();
 }
 async function confirmRecovery(){
  if(lock.current)return;lock.current=true;setBusy(true);setError(null);
  try{await recovered(await confirmRecoveryCommand(scope));}catch(e){if(current())setError('原恢复申请尚未确认：'+(e as Error).message);}finally{lock.current=false;if(current()){setBusy(false);syncPending();}}
 }
 async function choose(id:string,group:GroupDefinition|null=null){
  if(locked)return;const epoch=++selectionEpoch.current;setInstallation(id);setSelected(group);setOptions(null);setPolicy('');setMessage(null);setError(null);setConfirmRetire(false);if(group)setCron(group.body.cron);
  if(!id)return;
  try{const runtime=await assetControlClient.getRuntimeInstallation(id);if(!current()||epoch!==selectionEpoch.current)return;
   if(!runtime.binding)throw new Error('该安装尚无运行配置，请先完成安装配置。');
   if(group&&runtime.binding.generation!==group.body.generation)throw new Error('该数据组属于历史安装代次，仍可停用或退役，不能用新代次覆盖。');
   const value=await groupOptions(scope,id,runtime.binding.generation);if(!current()||epoch!==selectionEpoch.current)return;
   setOptions(value);setPolicy(group?value.policies.find(p=>p.contentHash===group.body.policyRef.contentHash)?.contentHash||'':value.policies.length===1?value.policies[0].contentHash:'');
  }catch(e){if(current()&&epoch===selectionEpoch.current)setError((e as Error).message);}
 }
 async function operate(intent:GroupIntent){
  if(lock.current||locked)return;
  if(intent==='configure'&&!canSave)return;
  if(intent!=='configure'&&!selected)return;
  lock.current=true;setBusy(true);setError(null);setMessage(null);
  try{
   const id=selected?.body.definitionId||crypto.randomUUID();
   const body=intent==='configure'?{expectedRef:selected?.ref||null,cron,policyRef:options!.policies.find(p=>p.contentHash===policy)!,members:options!.members.map(m=>({scheduleId:m.scheduleId,bindingRef:m.bindingRef}))}:{expectedRef:selected!.ref};
   const result=await submitGroupCommand(scope,id,intent,body);
   if(!current())return;setConfirmRetire(false);setMessage('原操作回执已核对。'+labels[result.body.state]);const latest=await readGroup(scope,id);if(!current())return;setSelected(latest);setCron(latest.body.cron);await reload();
  }catch(e){if(current())setError((e as Error).message);}finally{lock.current=false;if(current()){setBusy(false);syncPending();}}
 }
 async function confirm(){
  if(lock.current)return;lock.current=true;setBusy(true);setError(null);
  try{const result=await confirmGroupCommand(scope);if(!current())return;setMessage('已找到并核对原操作回执。');const latest=await readGroup(scope,result.body.definitionId);if(!current())return;setSelected(latest);setInstallation(latest.body.installationId);setCron(latest.body.cron);await reload();}
  catch(e){if(current())setError('原操作尚未确认：'+(e as Error).message);}finally{lock.current=false;if(current()){setBusy(false);syncPending();}}
 }
 const occupied=options?.members.some(m=>m.definitionId&&m.definitionId!==selected?.body.definitionId)??false;
 const canSave=!locked&&options?.status==='ready'&&!!policy&&!!cron.trim()&&!occupied&&(!selected||selected.body.state==='disabled');
 const name=(id:string)=>installations.find(i=>i.installationId===id)?.displayName||'已安装数据组';
 return <section className="snapshot-groups" aria-label="整组采集配置">
  <header className="snapshot-groups__header"><div><h2>整组采集</h2><p>让商品、订单、客户等十二类来源按同一计划准备一致数据。</p></div><button type="button" disabled={busy} onClick={()=>void reload().catch(e=>setError(e.message))}>刷新配置</button></header>
  <p className="snapshot-groups__notice">选择已保存的数据组，查看当前运行情况。启用配置不代表数据已采集或业务已完成。</p>
  {selected&&<RuntimeStatus key={JSON.stringify(selected.ref)} scope={scope} group={selected} blocked={locked} onConfirmed={recovered} onBusy={value=>{if(current())setBusy(value);}}/>}
  {error&&<p className="snapshot-groups__error" role="alert">{error}</p>}{message&&<p role="status">{message}</p>}
  {pending&&<aside className="snapshot-groups__pending"><strong>有一项待确认操作</strong><p>本地仅保留原请求以核对结果，不会自动重发。请先核对，再进行下一项操作。</p><button type="button" disabled={busy} onClick={()=>void confirm()}>核对原操作</button><details><summary>原操作标识</summary><code>{pending.key}</code></details></aside>}
  {recoveryPending&&<aside className="snapshot-groups__pending"><strong>有一项待确认恢复申请</strong><p>仅核对原申请回执，不会再次提交。请先确认，再办理其他配置或恢复。</p><button type="button" disabled={busy} onClick={()=>void confirmRecovery()}>核对原恢复申请</button><details><summary>原恢复申请标识</summary><code>{recoveryPending.key}</code></details></aside>}
  <div className="snapshot-groups__layout"><div className="snapshot-groups__list"><h3>已保存的配置</h3>{!groups.length&&<p>尚无数据组配置；请先选择已安装实例检查来源。</p>}
   {groups.map(group=><button className={'snapshot-groups__item'+(selected?.body.definitionId===group.body.definitionId?' is-selected':'')} type="button" key={group.body.definitionId} disabled={locked} onClick={()=>void choose(group.body.installationId,group)}><strong>{name(group.body.installationId)}</strong><span>{labels[group.body.state]} · 版本 {group.body.revision}</span><small>{group.body.cron} · 上海时区 · 十二类来源</small></button>)}
   {next&&<button type="button" disabled={busy} onClick={()=>void listGroups(scope,next).then(page=>{if(current()){setGroups(old=>[...old,...page.items.filter(x=>!old.some(y=>x.body.definitionId===y.body.definitionId))]);setNext(page.nextCursor);}}).catch(e=>{if(current())setError(e.message);})}>加载更多配置</button>}
  </div><div className="snapshot-groups__editor"><div className="snapshot-groups__header"><h3>{selected?'编辑已保存配置':'创建数据组'}</h3>{selected&&<button type="button" disabled={locked} onClick={()=>void choose('')}>新建配置</button>}</div>
   <label>已安装实例<select aria-label="已安装实例" value={installation} disabled={locked||!!selected} onChange={e=>void choose(e.target.value)}><option value="">选择已安装实例</option>{installations.map(i=><option key={i.installationId} value={i.installationId}>{i.displayName}</option>)}{installation&&!installations.some(i=>i.installationId===installation)&&<option value={installation}>{name(installation)}</option>}</select></label>
   {installations.length<installationTotal&&<button type="button" disabled={locked} onClick={()=>void assetControlClient.listInstallations({state:'active',offset:installations.length,limit:50}).then(page=>{if(current()){setInstallations(old=>[...old,...page.items]);setInstallationTotal(page.total);}}).catch(e=>{if(current())setError(e.message);})}>加载更多安装实例</button>}
   {options?.status==='incomplete'&&<div role="status"><h4>来源尚未就绪</h4>{options.missing.length>0&&<p>缺少：{options.missing.map(id=>getPipelineDisplayName(id)).join('、')}</p>}{options.ambiguous.length>0&&<p>存在重复绑定：{options.ambiguous.map(id=>getPipelineDisplayName(id)).join('、')}</p>}<p>需先通过正式来源与调度配置补齐，当前不能保存整组计划。</p></div>}
   {options?.status==='policy_unavailable'&&<p role="status">当前安装包没有适用于这十二类来源的有效关系策略。</p>}
   {occupied&&<p role="status">部分来源已属于其他数据组，请先选择对应配置核对。</p>}
   {options&&<><label>已安装关系策略<select aria-label="已安装关系策略" value={policy} disabled={locked||selected?.body.state==='retired'} onChange={e=>setPolicy(e.target.value)}><option value="">选择可用关系策略</option>{options.policies.map((p,i)=><option key={p.contentHash} value={p.contentHash}>关系策略 {i+1} · 版本 {p.revision}</option>)}</select></label><details><summary>查看已核对的来源（{options.members.length}/12）</summary><ul>{options.members.map(m=><li key={m.scheduleId}>{getPipelineDisplayName(m.pipelineId)}</li>)}</ul></details></>}
   <label>采集周期（上海时区）<input aria-label="采集周期" value={cron} disabled={locked||selected?.body.state==='retired'} onChange={e=>setCron(e.target.value)}/></label><div className="snapshot-groups__actions"><button type="button" disabled={locked||selected?.body.state==='retired'} onClick={()=>setCron('0 * * * *')}>每小时</button><button type="button" disabled={locked||selected?.body.state==='retired'} onClick={()=>setCron('0 8 * * *')}>每天 08:00</button></div>
   <div className="snapshot-groups__actions"><button type="button" disabled={!canSave} onClick={()=>void operate('configure')}>保存为停用配置</button>{selected?.body.state==='disabled'&&<button type="button" disabled={locked||options?.status!=='ready'||cron!==selected.body.cron||policy!==selected.body.policyRef.contentHash||options.members.some(m=>!selected.body.members.some(saved=>saved.scheduleId===m.scheduleId&&saved.bindingRef.contentHash===m.bindingRef.contentHash))} onClick={()=>void operate('enable')}>启用配置</button>}{selected?.body.state==='enabled'&&<button type="button" disabled={locked} onClick={()=>void operate('disable')}>停用配置</button>}{selected?.body.state==='disabled'&&<button type="button" disabled={locked} onClick={()=>setConfirmRetire(true)}>退役配置</button>}</div>
   {confirmRetire&&<div className="snapshot-groups__pending"><p>退役会释放来源归属，保留历史回执；仅在所有原运行已停止后允许执行。</p><button type="button" disabled={locked} onClick={()=>void operate('retire')}>确认退役</button><button type="button" disabled={locked} onClick={()=>setConfirmRetire(false)}>取消</button></div>}
   {selected&&<details><summary>查看配置标识</summary><code>{selected.body.definitionId}</code><p>版本 {selected.body.revision} · {labels[selected.body.state]}</p></details>}
  </div></div>
 </section>;
}

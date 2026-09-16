import { useCallback,useEffect,useRef,useState } from 'react';
import { assetControlClient } from '../../api/assetControl/client';
import type { InstallationListItem } from '../../api/assetControl/types';
import { confirmGroupCommand,groupOptions,groupScope,listGroups,readGroup,pendingGroupCommand,submitGroupCommand,type GroupDefinition,type GroupIntent,type GroupOptions,type GroupScope,type PendingGroupCommand } from '../../api/snapshotSchedules';
import { getPipelineDisplayName } from './pipelineMeta';
import './SnapshotSchedulesPanel.css';

const labels={disabled:'已配置 · 已停用',enabled:'已启用配置',retired:'已退役'};
function scopeOrNull(){try{return groupScope();}catch{return null;}}
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
 const [confirmRetire,setConfirmRetire]=useState(false);
 const lock=useRef(false),mounted=useRef(true),selectionEpoch=useRef(0);
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;selectionEpoch.current+=1;};},[]);
 const current=()=>mounted.current&&JSON.stringify(scopeOrNull())===JSON.stringify(scope);
 const syncPending=useCallback(()=>{try{setPending(pendingGroupCommand(scope));setPendingError(false);}catch(e){setPendingError(true);setError((e as Error).message);}},[scope]);
 const reload=useCallback(async()=>{const page=await listGroups(scope);if(!mounted.current)return;setGroups(page.items);setNext(page.nextCursor);},[scope]);
 useEffect(()=>{syncPending();void reload().catch(e=>{if(mounted.current)setError(e.message);});void assetControlClient.listInstallations({state:'active',limit:50}).then(page=>{if(current()){setInstallations(page.items);setInstallationTotal(page.total);}}).catch(e=>{if(current())setError(e.message);});},[reload,scope,syncPending]);
 const locked=busy||!!pending||pendingError;
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
  <p className="snapshot-groups__notice" role="status">当前提供配置管理；执行调度尚未接通。启用配置不代表数据已采集或业务已完成。</p>
  {error&&<p className="snapshot-groups__error" role="alert">{error}</p>}{message&&<p role="status">{message}</p>}
  {pending&&<aside className="snapshot-groups__pending"><strong>有一项待确认操作</strong><p>本地仅保留原请求以核对结果，不会自动重发。请先核对，再进行下一项操作。</p><button type="button" disabled={busy} onClick={()=>void confirm()}>核对原操作</button><details><summary>原操作标识</summary><code>{pending.key}</code></details></aside>}
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

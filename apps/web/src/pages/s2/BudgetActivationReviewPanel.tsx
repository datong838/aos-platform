import { useEffect, useRef, useState } from 'react';
import { getAuthRevision, getTenant } from '../../api/tenant';
import { inquireBudget, readBudgetSource, restoreBudgetReference, saveBudgetReference, submitBudget,
 type BudgetMode, type BudgetRef, type BudgetResult, type BudgetSource } from '../../api/aipBudgetActivation';

function identity(){const t=getTenant();return JSON.stringify([t.orgId,t.projectId,t.subject,getAuthRevision()]);}
function slot(ref:BudgetRef){const t=getTenant();return JSON.stringify([t.orgId,t.projectId,t.subject,ref]);}
const action:Record<BudgetMode,string>={preview:'生成预算预览',decision:'提交复核决定',revoke:'撤销此批准'};

export function BudgetActivationReviewPanel(){
 const initial=useRef(restoreBudgetReference(typeof window==='undefined'?'':window.location.search));
 const [mode,setMode]=useState<BudgetMode>(initial.current?.ref.mode??'preview');
 const [id,setId]=useState(initial.current?.ref.id??'');
 const [checker,setChecker]=useState(''),[decision,setDecision]=useState(''),[reason,setReason]=useState('');
 const [source,setSource]=useState<BudgetSource|null>(null),[ref,setRef]=useState<BudgetRef|null>(initial.current?.ref??null);
 const [result,setResult]=useState<BudgetResult|null>(null),[busy,setBusy]=useState(false);
 const [message,setMessage]=useState('先读取审批对象并核对原请求，再确认本次操作。预算生效仍受独立运行门控制。');
 const epoch=useRef(0),busyRef=useRef(false),attempted=useRef(new Set<string>());
 const sourceIdentity=useRef('');
 function invalidate(){epoch.current++;busyRef.current=false;setBusy(false);setSource(null);setResult(null);setRef(null);sourceIdentity.current='';}
 useEffect(()=>{
  const changed=()=>{invalidate();setId('');setChecker('');setDecision('');setReason('');setMessage('身份或工作区已变化，请重新读取审批对象。');};
  window.addEventListener('aos-auth-updated',changed);window.addEventListener('aos-tenant-updated',changed);
  return()=>{epoch.current++;busyRef.current=false;window.removeEventListener('aos-auth-updated',changed);window.removeEventListener('aos-tenant-updated',changed);};
 },[]);
 async function run(task:(current:()=>boolean)=>Promise<{ref:BudgetRef;result:BudgetResult;source?:BudgetSource}>){
  if(busyRef.current)return;
  busyRef.current=true;setBusy(true);const generation=epoch.current,actor=identity();
  const current=()=>generation===epoch.current&&actor===identity();
  try{
   const value=await task(current);if(!current())return;
   if(value.result.status==='not_attempted'&&attempted.current.has(slot(value.ref)))throw new Error('曾尝试提交但原记录未确认，请核对服务端持久记录，禁止重发');
   setRef(value.ref);setResult(value.result);
   if(value.source){setSource(value.source);sourceIdentity.current=actor;}
   setMessage(value.result.status==='observed'?'已确认原操作的历史记录；这不表示预算已经生效。':
    value.result.status==='not_attempted'?'此产品请求尚未登记，请核对下方内容并明确选择。':
    value.result.status==='conflict'?'原请求与记录不一致，已冻结提交，请核对原审批对象。':'原操作结果尚未确认，只能继续查询，不能重复提交。');
  }catch(error){if(current()){setResult(null);setMessage(`尚未确认：${(error as Error).message}。请只读查询，勿重复提交。`);}}
  finally{if(current()){busyRef.current=false;setBusy(false);}}
 }
 useEffect(()=>{
  const restored=initial.current;if(!restored)return;
  if(restored.attempted)attempted.current.add(slot(restored.ref));
  void run(async()=>({ref:restored.ref,result:await inquireBudget(restored.ref)}));
 },[]);
 async function load(){
  if(busyRef.current)return;setSource(null);setResult(null);
  await run(async current=>{const value=await readBudgetSource(mode,id.trim());
   if(!current())throw new Error('身份已变化');
   // A restored request keeps its original revision; reading a newer head never changes it silently.
   if(ref&&ref.mode==='preview'&&ref.id===value.ref.id&&attempted.current.has(slot(ref))&&JSON.stringify(ref)!==JSON.stringify(value.ref))throw new Error('当前版本已变化，请先核对 URL 中原请求，不能自动换版本提交');
   saveBudgetReference(value.ref,attempted.current.has(slot(value.ref)));
   return {source:value,ref:value.ref,result:await inquireBudget(value.ref)};
  });
 }
 function eligible(){
  if(!source||sourceIdentity.current!==identity()||result?.status!=='not_attempted'||attempted.current.has(slot(source.ref)))return false;
  const p=source.preview,t=getTenant();
  if(mode==='preview')return checker.trim()===checker&&checker.length>0&&checker.length<=200&&checker!==t.subject
    &&Date.parse(source.target.effectiveFrom)<=Date.now()&&Date.parse(source.target.effectiveUntil)>Date.now();
  if(mode==='decision')return !!p&&t.subject===p.checkerSubject&&Date.parse(p.expiresAt)>Date.now()&&['approved','rejected'].includes(decision);
  return !!p&&!!source.decision&&source.decision.decision==='approved'&&source.revoked===false
    &&typeof t.subject==='string'&&[p.makerSubject,p.checkerSubject].includes(t.subject)&&reason.trim()===reason&&reason.length>0&&reason.length<=500;
 }
 async function submit(){
  if(busyRef.current||!eligible()||!source)return;
  const original=source;attempted.current.add(slot(original.ref));setResult({status:'unresolved'});
  await run(async()=>{saveBudgetReference(original.ref,true);
   return {ref:original.ref,result:await submitBudget(original,{checker,decision,reason})};
  });
 }
 function follow(next:BudgetMode,nextId:string){invalidate();setMode(next);setId(nextId);setChecker('');setDecision('');setReason('');
  const nextRef={mode:next,id:nextId};setRef(nextRef);saveBudgetReference(nextRef,false);setMessage('请读取此审批记录的内容，再由适用账号操作。');}
 const target=source?.target;
 return <section className="card" aria-label="预算审批与恢复" style={{padding:18,marginTop:16}}>
  <h2>预算审批与恢复</h2>
  <p>预览、复核和撤销均保留原请求，可刷新后查询。批准仅记录审核意见；当前不会激活预算、启动模型或产生费用。</p>
  <div style={{display:'flex',flexWrap:'wrap',gap:12}}>
   <label>操作<select aria-label="预算审批操作" disabled={busy} value={mode} onChange={e=>{invalidate();setMode(e.target.value as BudgetMode);setId('');setDecision('');setReason('');}}>
    <option value="preview">准备预算预览</option><option value="decision">独立复核预览</option><option value="revoke">撤销批准</option>
   </select></label>
   <label>{mode==='preview'?'预算 ID':mode==='decision'?'预览 ID':'批准记录 ID'}<input aria-label="预算或审批记录 ID" value={id} disabled={busy} maxLength={160} onChange={e=>{invalidate();setId(e.target.value);}}/></label>
   {mode==='preview'&&<label>独立审核人账号<input aria-label="独立审核人账号" value={checker} maxLength={200} disabled={busy} onChange={e=>{setChecker(e.target.value);setResult(null);}}/></label>}
  </div>
  <div style={{display:'flex',flexWrap:'wrap',gap:8,marginTop:12}}>
   <button type="button" className="btn" disabled={busy||!id.trim()} onClick={()=>void load()}>读取审批对象</button>
   <button type="button" className="btn" disabled={busy||!ref} onClick={()=>{if(ref)void run(async()=>({ref,result:await inquireBudget(ref)}));}}>查询原请求结果</button>
  </div>
  {target&&<div aria-label="预算审批内容" style={{marginTop:12}}>
   <p>预算 {target.budgetId} · 候选第 {target.revision} 版 · 日上限 ¥{(target.dailyLimitMinor/100).toFixed(2)} · 月上限 ¥{(target.monthlyLimitMinor/100).toFixed(2)}</p>
   <p>有效期：{target.effectiveFrom} 至 {target.effectiveUntil}；告警阈值 {target.alertThresholdPct}%；负责人 {target.owner}。</p>
   <p>超预算审批人：{target.overBudgetApprover}；未知用量保持禁入，超限停止。</p>
   {source?.preview&&<p>发起人：{source.preview.makerSubject}；独立审核人：{source.preview.checkerSubject}；预览到期：{source.preview.expiresAt}。{Date.parse(source.preview.expiresAt)<=Date.now()?'预览已过期，不能批准。':''}</p>}
   {source?.decision&&<p>历史决定：{source.decision.decision==='approved'?'批准':'拒绝'}；{source.revoked?'已撤销':'此快照未见撤销记录'}。历史批准不代表当前执行授权。</p>}
  </div>}
  {mode==='decision'&&<label>复核意见<select aria-label="预算复核意见" value={decision} disabled={busy} onChange={e=>setDecision(e.target.value)}>
   <option value="">请明确选择</option><option value="approved">批准此预览</option><option value="rejected">拒绝此预览</option>
  </select></label>}
  {mode==='revoke'&&<label>撤销原因<input aria-label="预算撤销原因" value={reason} maxLength={500} disabled={busy} onChange={e=>setReason(e.target.value)}/></label>}
  <div style={{marginTop:12}}><button type="button" className="btn btn-primary" disabled={busy||!eligible()} onClick={()=>void submit()}>{action[mode]}</button></div>
  <p role="status">{message}</p>
  {result?.status==='observed'&&<div><p>原记录：<code>{result.id}</code></p>
   {mode!=='revoke'&&<button type="button" className="btn" disabled={busy} onClick={()=>follow(mode==='preview'?'decision':'revoke',result.id)}>{mode==='preview'?'查看此预览进行复核':'查看此决定与撤销'}</button>}
  </div>}
 </section>;
}

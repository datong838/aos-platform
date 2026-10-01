import { useEffect, useRef, useState } from 'react';
import { getTenant } from '../../api/tenant';
import { inquireCost, readCostReview, restoreCostReference, saveCostReference, submitCost,
 type CostRef, type CostReview, type CostResult } from '../../api/aipBudgetCost';
import { budgetIdentity, useBudgetRequestGuard } from './useBudgetRequestGuard';

export function BudgetCostReviewPanel(){
 const initial=useRef(restoreCostReference(typeof window==='undefined'?'':window.location.search));
 const [operation,setOperation]=useState<CostRef['operation']>(initial.current?.ref.operation??'decide'),[id,setId]=useState(initial.current?.ref.id??'');
 const [choice,setChoice]=useState(''),[reason,setReason]=useState(''),[ref,setRef]=useState<CostRef|null>(initial.current?.ref??null);
 const [source,setSource]=useState<CostReview|null>(null),[result,setResult]=useState<CostResult|null>(null),sourceIdentity=useRef('');
 const [consumption,setConsumption]=useState<CostResult|null>(null);
 const [message,setMessage]=useState('先读取费用提议与原请求，再由适用账号明确复核。');
 function clear(){setConsumption(null);setSource(null);setResult(null);setRef(null);sourceIdentity.current='';}
 const guard=useBudgetRequestGuard(()=>{clear();setId('');setChoice('');setReason('');setMessage('身份或工作区已变化，请重新读取费用提议。');});
 function invalidate(){guard.invalidate();clear();}
 async function run(task:(current:()=>boolean)=>Promise<{ref:CostRef;result:CostResult;source?:CostReview;consumption?:CostResult}>){
  const current=guard.begin();if(!current)return;const actor=budgetIdentity();
  try{const v=await task(current);if(!current())return;guard.checkResult(v.ref,v.result.status);setRef(v.ref);setResult(v.result);
   if(v.consumption)setConsumption(v.consumption);
   if(v.source){setSource(v.source);sourceIdentity.current=actor;}
   setMessage(v.result.status==='observed'?(v.ref.operation==='configure'?'已确认费用配置的历史回执；不会启动模型或业务，当前执行仍须核验授权与预算。':v.ref.operation==='consume'?'已确认预算启用的历史回执；当前执行仍须核验批准、配置和预算，不会自动启动业务。':'已确认原操作的历史记录；这不表示预算已经生效。'):v.result.status==='not_attempted'?'原请求尚未登记，请核对提议并明确选择。':v.result.status==='conflict'?'原请求发生冲突，提交已冻结，请核对原记录。':'原结果尚未确认，只能查询，禁止重复提交。');
  }catch(e){if(current()){setResult(null);setMessage(`尚未确认：${(e as Error).message}。请只读查询，勿重复提交。`);}}
  finally{guard.finish(current);}
 }
 useEffect(()=>{const restored=initial.current;if(!restored)return;if(restored.attempted)guard.markAttempted(restored.ref);
  void run(async()=>({ref:restored.ref,result:await inquireCost(restored.ref)}));},[]);
 async function load(){if(guard.busyRef.current)return;setSource(null);setResult(null);setConsumption(null);
  await run(async current=>{const value=await readCostReview(id.trim());if(!current())throw new Error('身份已变化');
   const next={id:value.proposal.proposalId,operation};saveCostReference(next,guard.attempted(next));
   const consumed=operation==='configure'?await inquireCost({id:next.id,operation:'consume'},value):undefined;
   if(!current())throw new Error('身份已变化');
   return {ref:next,source:value,consumption:consumed,result:await inquireCost(next,value,consumed?.status==='observed'?consumed:undefined)};
  });
 }
 function eligible(){
  if(!source||!ref||sourceIdentity.current!==budgetIdentity()||result?.status!=='not_attempted'||guard.attempted(ref))return false;
  const p=source.proposal,actor=getTenant().subject;
  if(operation==='configure'&&(consumption?.status!=='observed'||!consumption.budgetRef))return false;
  if(operation==='consume'||operation==='configure')return actor===p.proposal.makerSubject&&source.decision?.decision==='approved'&&source.revocation===null&&Date.parse(source.decision.expiresAt)>Date.now()&&choice===operation;
  if(operation==='decide')return actor===p.proposal.checkerSubject&&source.decision===null&&Date.parse(p.expiresAt)>Date.now()&&['approved','rejected'].includes(choice);
  return source.decision?.decision==='approved'&&source.revocation===null&&typeof actor==='string'
   &&[p.proposal.makerSubject,p.proposal.checkerSubject].includes(actor)&&reason.length>0&&reason.length<=500&&reason.trim()===reason&&!/[\u0000-\u001f\u007f]/.test(reason);
 }
 async function submit(){if(guard.busyRef.current||!eligible()||!source||!ref)return;
  const original=ref;guard.markAttempted(original);setResult({status:'unresolved'});
  await run(async()=>{saveCostReference(original,true);return {ref:original,result:await submitCost(original,source,choice,reason,operation==='configure'?consumption??undefined:undefined)};});
 }
 const p=source?.proposal.proposal,t=p?.target,b=p?.basis;
 return <section className="card" aria-label="费用风险审核与恢复" style={{padding:18,marginTop:16}}>
  <h2>费用风险审核与恢复</h2>
  <p>开发风险额度是待审核的费用承担范围，不是实际账单或 Provider 计费上限。批准仅记录审核意见；发起人可另行启用已批准预算。启用预算不会启动模型或业务，执行时仍须核验当前授权与额度。</p>
  <div style={{display:'flex',flexWrap:'wrap',gap:12}}>
   <label>操作<select aria-label="费用审核操作" value={operation} disabled={guard.busy} onChange={e=>{invalidate();setOperation(e.target.value as CostRef['operation']);setChoice('');setReason('');}}>
    <option value="decide">独立复核费用提议</option><option value="revoke">撤销费用批准</option><option value="consume">启用已批准预算</option><option value="configure">生成费用配置</option>
   </select></label>
   <label>费用提议 ID<input aria-label="费用提议 ID" maxLength={160} value={id} disabled={guard.busy} onChange={e=>{invalidate();setId(e.target.value);setChoice('');setReason('');}}/></label>
  </div>
  <div style={{display:'flex',flexWrap:'wrap',gap:8,marginTop:12}}>
   <button type="button" className="btn" disabled={guard.busy||!id.trim()} onClick={()=>void load()}>读取费用提议</button>
   <button type="button" className="btn" disabled={guard.busy||!ref} onClick={()=>{if(ref)void run(async()=>({ref,result:await inquireCost(ref,source??undefined,operation==='configure'&&consumption?.status==='observed'?consumption:undefined)}));}}>查询费用原请求</button>
  </div>
  {p&&t&&b&&<div aria-label="费用提议内容">
   <p>预算 {t.budgetId} · 候选第 {t.revision} 版 · 日上限 ¥{(t.dailyLimitMinor/100).toFixed(2)} · 月上限 ¥{(t.monthlyLimitMinor/100).toFixed(2)}</p>
   <p>Provider：{b.provider.assetId}（第 {b.provider.revision} 版）；模型：{b.providerModelId}</p>
   <p>单次风险 ¥{(b.perRequestRiskMinor/100).toFixed(2)} · 总风险 ¥{(b.totalRiskMinor/100).toFixed(2)} · 最多 {b.maxRequests} 次</p>
   <p>有效期：{t.effectiveFrom} 至 {t.effectiveUntil}；负责人 {t.owner}；超预算审批人 {t.overBudgetApprover}；告警 {t.alertThresholdPct}%。未知用量保持禁入，超限停止。</p>
   <p>发起人 {p.makerSubject}；独立审核人 {p.checkerSubject}；提议到期 {source.proposal.expiresAt}。{Date.parse(source.proposal.expiresAt)<=Date.now()?'提议已过期，不能批准。':''}</p>
   <p>日账户 {p.accounts.daily}；试点账户 {p.accounts.pilot}；来源仍须在实际启用时重新核验。</p>
   {source.decision&&<p>历史决定：{source.decision.decision==='approved'?'批准':'拒绝'}；{source.revocation?'已撤销':'此快照未见撤销记录'}。历史批准不代表当前执行授权。</p>}
   {source.revocation&&<p>撤销人 {source.revocation.actorSubject}；原因：{source.revocation.reason}</p>}
  </div>}
  {operation==='configure'&&<p>{consumption?.status==='observed'?'已观察到对应预算启用回执，可复核生成费用配置。':'须先确认此提议对应的预算已启用；缺少、冲突或未知回执时不能生成费用配置。'}</p>}
  {operation==='configure'?<label>费用配置确认<select aria-label="费用配置确认" value={choice} disabled={guard.busy} onChange={e=>setChoice(e.target.value)}><option value="">请明确选择</option><option value="configure">确认生成此批准对应的费用配置</option></select></label>:operation==='consume'?<label>预算启用确认<select aria-label="预算启用确认" value={choice} disabled={guard.busy} onChange={e=>setChoice(e.target.value)}><option value="">请明确选择</option><option value="consume">确认启用此批准对应的预算</option></select></label>:operation==='decide'?<label>复核意见<select aria-label="费用复核意见" value={choice} disabled={guard.busy} onChange={e=>setChoice(e.target.value)}>
   <option value="">请明确选择</option><option value="approved">批准此费用提议</option><option value="rejected">拒绝此费用提议</option>
  </select></label>:<label>撤销原因<input aria-label="费用撤销原因" maxLength={500} value={reason} disabled={guard.busy} onChange={e=>setReason(e.target.value)}/></label>}
  <div style={{marginTop:12}}><button type="button" className="btn btn-primary" disabled={guard.busy||!eligible()} onClick={()=>void submit()}>{operation==='configure'?'生成费用配置':operation==='consume'?'启用已批准预算':operation==='decide'?'提交费用复核':'撤销费用批准'}</button></div>
  <p role="status">{message}</p>{result?.status==='observed'&&<p>原记录：{result.id}</p>}
  {result?.status==='observed'&&result.priceRef&&result.policyRef&&<div aria-label="费用配置历史引用"><p>价格配置：{result.priceRef.assetId} · 第 {result.priceRef.revision} 版</p><p>预算策略：{result.policyRef.assetId} · 第 {result.policyRef.revision} 版</p><p>这些引用证明原配置已生成，不代表当前仍有效或业务已运行。</p></div>}
 </section>;
}

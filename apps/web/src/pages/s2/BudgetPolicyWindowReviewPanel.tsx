import {useEffect, useRef, useState, type CSSProperties} from 'react';
import * as windowApi from '../../api/aipBudgetPolicyWindow';
import type {PolicyWindowSource, WindowCommand, WindowDecisionReceipt, WindowGatewayStatus,
 WindowObservation, WindowOperation, WindowProposeReceipt, WindowReceiptLinks, WindowRef,
 WindowRequestIndex, WindowRevocationReceipt, WindowConsumeReceipt} from '../../api/aipBudgetPolicyWindow';
import {useBudgetRequestGuard} from './useBudgetRequestGuard';

const field:CSSProperties={display:'flex',flexDirection:'column',gap:6,flex:'1 1 240px',minWidth:0};
const flow:CSSProperties={display:'flex',flexWrap:'wrap',gap:12,marginTop:12};
const keyValid=(key:string)=>/^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$/.test(key);
const sameProposal=(a:{proposalId:string;proposalHash:string},b:{proposalId:string;proposalHash:string})=>a.proposalId===b.proposalId&&a.proposalHash===b.proposalHash;

/** Native records remain authority. This panel never starts a model or retries a write. */
export function BudgetPolicyWindowReviewPanel(){
 const initial=useRef(windowApi.restoreWindowReference(typeof window==='undefined'?'':window.location.search));
 const [operation,setOperation]=useState<WindowOperation>(initial.current?.ref.operation??'propose');
 const [key,setKey]=useState(initial.current?.ref.key??''),[parentId,setParentId]=useState('');
 const [from,setFrom]=useState(''),[until,setUntil]=useState(''),[choice,setChoice]=useState('');
 const [reason,setReason]=useState(''),[confirmation,setConfirmation]=useState('');
 const [gateway,setGateway]=useState<WindowGatewayStatus|null>(null),[source,setSource]=useState<PolicyWindowSource|null>(null);
 const [prepared,setPrepared]=useState<WindowProposeReceipt|null>(null),[decision,setDecision]=useState<WindowDecisionReceipt|null>(null);
 const [revocation,setRevocation]=useState<WindowRevocationReceipt|null>(null),[consumed,setConsumed]=useState<WindowConsumeReceipt|null>(null);
 const [reference,setReference]=useState<WindowRef|null>(initial.current?.ref??null);
 const [frozen,setFrozen]=useState<WindowRef|null>(initial.current?.ref??null);
 const [observation,setObservation]=useState<WindowObservation|null>(null),[history,setHistory]=useState<WindowRequestIndex[]>([]);
 const [message,setMessage]=useState('先核对审核入口与父预算来源，再明确填写策略窗口。');
 function clearIdentity(){
  setGateway(null);setSource(null);setPrepared(null);setDecision(null);setRevocation(null);setConsumed(null);
  setObservation(null);setReference(null);setFrozen(null);setHistory([]);setKey('');setParentId('');setFrom('');setUntil('');
  setChoice('');setReason('');setConfirmation('');setMessage('身份或工作区已变化，请重新读取原记录。');
 }
 const guard=useBudgetRequestGuard(clearIdentity);
 async function read(task:(current:()=>boolean)=>Promise<void>){
  const current=guard.begin();if(!current)return;
  try{await task(current);}catch{if(current())setMessage('当前读取未确认，请核对入口或查询原操作；不会自动重发。');}
  finally{guard.finish(current);}
 }
 function links():WindowReceiptLinks{return prepared?{prepared,...(decision&&sameProposal(prepared,decision)?{decision}:{})}:{};}
 function accept(value:WindowObservation){
  setObservation(value);
  if(value.status!=='observed'){
   setFrozen(value.ref);setMessage('原策略结果尚未确认，只能查询原操作，禁止重复提交。');return;
  }
  const receipt=value.receipt;
  if(receipt.operation==='propose'){
   setPrepared(receipt);
   setDecision(old=>old&&sameProposal(old,receipt)?old:null);
   setRevocation(old=>old&&sameProposal(old,receipt)?old:null);
   setConsumed(old=>old&&sameProposal(old,receipt)?old:null);
  }else if(receipt.operation==='decide')setDecision(receipt);
  else if(receipt.operation==='revoke')setRevocation(receipt);
  else setConsumed(receipt);
  setFrozen(null);setMessage('已观察原操作的历史回执；当前身份、父预算、期限和批准仍由原生服务重新核验。');
 }
 async function query(ref:WindowRef){
  if(guard.busyRef.current)return;
  // A restored reference or an index row is always inquiry-only, even if a result is absent.
  guard.markAttempted(ref);setReference(ref);setOperation(ref.operation);setKey(ref.key);setFrozen(ref);
  setChoice('');setReason('');setConfirmation('');
  windowApi.saveWindowReference(ref,true);
  await read(async current=>{
   const result=await windowApi.inquireWindowRequest(ref,ref.operation==='propose'?{}:links());
   if(current())accept(result);
  });
 }
 useEffect(()=>{if(initial.current)void query(initial.current.ref);},[]);
 const matchedDecision=prepared&&decision&&sameProposal(prepared,decision)?decision:null;
 const revoked=!!(prepared&&revocation&&sameProposal(prepared,revocation));
 const configured=!!(prepared&&consumed&&sameProposal(prepared,consumed));
 function command():WindowCommand|null{
  try{
   if(!keyValid(key))return null;
   if(operation==='propose')return source?windowApi.policyWindowProposalCommand(source,key,from,until):null;
   if(!prepared)return null;
   if(operation==='revoke')return matchedDecision&&!revoked?windowApi.windowRevocationCommand(prepared,matchedDecision,key,reason):null;
   if(revoked||configured||Date.parse(prepared.proposal.expiresAt)<=Date.now())return null;
   if(operation==='decide')return !matchedDecision?windowApi.windowDecisionCommand(prepared,key,choice):null;
   return matchedDecision?windowApi.windowConsumeCommand(prepared,matchedDecision,key,confirmation==='consume'):null;
  }catch{return null;}
 }
 const canSubmit=!!gateway?.writerEnabled&&!guard.busy&&!frozen&&!guard.attempted({operation,key})&&command()!==null;
 async function submit(){
  if(!gateway?.writerEnabled||frozen||guard.attempted({operation,key}))return;
  const payload=command();if(!payload)return;
  const current=guard.begin();if(!current)return;
  const ref:WindowRef={operation,key};
  guard.markAttempted(ref);setReference(ref);setFrozen(ref);setObservation(null);
  setChoice('');setConfirmation('');
  try{
   windowApi.saveWindowReference(ref,true);
   const result=await windowApi.submitWindowOperation(ref.operation,payload,links());
   if(current())accept(result);
  }catch{if(current())setMessage('原策略结果尚未确认，只能查询原操作，禁止重复提交。');}
  finally{guard.finish(current);}
 }
 const locked=guard.busy||!!frozen;
 const p=prepared?.proposal;
 return <section aria-label="预算策略子窗口审核" style={{marginTop:24,padding:20,border:'1px solid #dce4ee',borderRadius:12,background:'#fff',overflowWrap:'anywhere'}}>
  <h3 style={{marginTop:0,color:'#1557b0'}}>预算策略与价格窗口</h3>
  <p>共享原预算，不增加预算。提议、审核、生成配置与撤销分别确认；不会自动批准或启动模型、业务。</p>
  <div style={flow}>
   <button type="button" className="btn" disabled={guard.busy} onClick={()=>void read(async current=>{setGateway(null);const value=await windowApi.readWindowGatewayStatus();if(current()){setGateway(value);setMessage(value.writerEnabled?'入口配置可接收操作，仍须原生授权核验。':'入口未开启写入，可继续查询原记录。');}})}>核对审核入口</button>
   <button type="button" className="btn" disabled={guard.busy} onClick={()=>void read(async current=>{const rows=await windowApi.listWindowRequests();if(current())setHistory(rows);})}>读取原操作列表</button>
  </div>
  <p>审核入口：{gateway?(gateway.writerEnabled?'配置已开启（不代表获准写入）':'写入关闭'):'未核对'}</p>
  <div style={flow}>
   <label style={field}>父费用提议编号<input aria-label="父费用提议编号" value={parentId} maxLength={200} disabled={locked} onChange={e=>{setParentId(e.target.value);setSource(null);}}/></label>
   <button type="button" className="btn" disabled={locked||!parentId} onClick={()=>void read(async current=>{setSource(null);const value=await windowApi.readPolicyWindowSource(parentId);if(current())setSource(value);})}>读取父预算来源</button>
  </div>
  {source&&<div aria-label="策略父预算来源">
   <p>父提议：{source.parent.proposalId}；历史意见：{source.parent.decision}；原生父预算核验尚未执行。</p>
   <p>来源状态：{source.state==='observed'?'已读取元数据':'当前不可用于提议'}；{source.blockers.join(' · ')}</p>
   <p>历史费用发起人：{source.parent.proposal.makerSubject}；历史审核人：{source.parent.proposal.checkerSubject}</p>
  </div>}
  <div style={flow}>
   <label style={field}>策略操作<select aria-label="策略操作" value={operation} disabled={locked} onChange={e=>{setOperation(e.target.value as WindowOperation);setKey('');setChoice('');setReason('');setConfirmation('');}}>
    <option value="propose">提交策略提议</option><option value="decide">独立审核策略</option><option value="consume">生成成对策略与价格</option><option value="revoke">撤销策略批准</option>
   </select></label>
   <label style={field}>策略操作编号<input aria-label="策略操作编号" value={key} disabled={locked} maxLength={120} onChange={e=>setKey(e.target.value)}/></label>
  </div>
  {operation==='propose'&&<div style={flow}>
   <label style={field}>策略开始时间<input aria-label="策略开始时间" placeholder="明确填写 UTC 时间" value={from} disabled={locked} onChange={e=>setFrom(e.target.value)}/></label>
   <label style={field}>策略结束时间<input aria-label="策略结束时间" placeholder="明确填写 UTC 时间" value={until} disabled={locked} onChange={e=>setUntil(e.target.value)}/></label>
  </div>}
  {p&&prepared&&<div aria-label="原生策略提议" style={{marginTop:16,padding:12,background:'#f5f8fc',borderRadius:8}}>
   <h4>原生提议历史</h4>
   <p>提议：{prepared.proposalId}；父费用提议：{p.parent.costProposalId}；原预算：{p.parent.budgetRef.assetId} / 第 {p.parent.budgetRef.revision} 版</p>
   <p>单次风险 {windowApi.formatWindowRiskMinor(p.parent.risk.perRequestRiskMinor)}；总风险 {windowApi.formatWindowRiskMinor(p.parent.risk.totalRiskMinor)}；最多 {p.parent.risk.maxRequests} 次。共享原预算，不新增额度。</p>
   <p>Provider：{p.parent.providerRef.assetId} / 第 {p.parent.providerRef.revision} 版；模型：{p.parent.providerModelId}；负责人：{p.parent.owner}</p>
   <p>父窗口：{p.parent.budgetWindow.effectiveFrom} 至 {p.parent.budgetWindow.effectiveUntil}</p>
   <p>策略窗口：{p.request.effectiveFrom} 至 {p.request.effectiveUntil}；提议到期：{p.expiresAt}；{Date.parse(p.expiresAt)<=Date.now()?'已过期，不能批准或生成配置。':''}</p>
   <p>新提议发起人：{p.makerSubject}；独立审核人：{p.checkerSubject}；创建时间：{p.createdAt}</p>
   <p>批准槽位：{p.approvalSlot}；成对摘要：{p.targetPairHash}</p>
   <p>策略：{p.targets.policy.policyId}；价格：{p.targets.price.priceSnapshotId}。未知价格不代表免费；未知价格或用量保持禁入，超限停止。</p>
   <details><summary>核对完整目标与引用</summary><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{JSON.stringify({parent:p.parent,targets:p.targets,proposalHash:prepared.proposalHash,requestHash:p.requestHash},null,2)}</pre></details>
  </div>}
  {decision&&<p aria-label="策略审核历史">策略审核历史：{decision.decision==='approved'?'批准':'拒绝'}；{decision.decisionId}。历史意见不代表当前批准仍有效。</p>}
  {consumed&&<p aria-label="策略配置历史">配置历史：策略 {consumed.policyRef.assetId} / 价格 {consumed.priceRef.assetId}；{consumed.receiptId}。不代表模型或业务已运行。</p>}
  {revocation&&<p aria-label="策略撤销历史">撤销历史：{revocation.receiptId}；该记录不证明正在运行的业务已经停止。</p>}
  {operation==='decide'&&<label style={{...field,marginTop:12}}>策略审核意见<select aria-label="策略审核意见" value={choice} disabled={locked} onChange={e=>setChoice(e.target.value)}><option value="">请明确选择</option><option value="approved">批准本次精确窗口</option><option value="rejected">拒绝本次提议</option></select></label>}
  {operation==='consume'&&<label style={{...field,marginTop:12}}>策略配置确认<select aria-label="策略配置确认" value={confirmation} disabled={locked} onChange={e=>setConfirmation(e.target.value)}><option value="">请明确确认</option><option value="consume">仅生成已批准的成对策略与价格配置</option></select></label>}
  {operation==='revoke'&&<label style={{...field,marginTop:12}}>策略撤销原因<input aria-label="策略撤销原因" value={reason} maxLength={500} disabled={locked} onChange={e=>setReason(e.target.value)}/></label>}
  <div style={flow}>
   <button type="button" className="btn" disabled={!canSubmit} onClick={()=>void submit()}>{operation==='propose'?'提交策略提议':operation==='decide'?'提交策略决定':operation==='consume'?'生成成对策略与价格':'撤销策略批准'}</button>
   <button type="button" className="btn" disabled={guard.busy||!reference} onClick={()=>{if(reference)void query(reference);}}>查询原策略操作</button>
  </div>
  <p role="status">{message}</p>
  {reference&&<p>原操作：{reference.operation} / {reference.key}；{observation?.status??'尚未确认'}</p>}
  {history.length>0&&<details open><summary>原操作列表（仅查询，不代表批准）</summary><ul>{history.map(item=><li key={item.operation+':'+item.idempotencyKey}><button type="button" className="btn" disabled={guard.busy||!!frozen} onClick={()=>void query({operation:item.operation,key:item.idempotencyKey})}>{item.operation} / {item.idempotencyKey}</button></li>)}</ul></details>}
 </section>;
}

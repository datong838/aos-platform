import {useEffect,useRef,useState} from 'react';
import {groupScope,readRecoveryContext,submitRecoveryCommand,type ExactRef,type GroupScope,type RecoveryContext,type RecoveryReceipt} from '../../api/snapshotSchedules';

const localInput=(value:string)=>{const date=new Date(value);return new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,23);};
export function SnapshotRecoveryPanel({scope,groupId,definitionRef,blocked,onConfirmed,onBusy}:{scope:GroupScope;groupId:string;definitionRef:ExactRef;blocked:boolean;onConfirmed:(receipt:RecoveryReceipt)=>Promise<void>|void;onBusy:(busy:boolean)=>void}){
 const [context,setContext]=useState<RecoveryContext|null>(null),[start,setStart]=useState(''),[end,setEnd]=useState('');
 const [error,setError]=useState<string|null>(null),[busy,setBusy]=useState(false);
 const mounted=useRef(false),lock=useRef(false),epoch=useRef(0);
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;epoch.current++;};},[]);
 const current=()=>{try{return mounted.current&&JSON.stringify(groupScope())===JSON.stringify(scope);}catch{return false;}};
 async function inspect(){
  if(blocked||lock.current)return;lock.current=true;setBusy(true);setError(null);setContext(null);const sequence=++epoch.current;
  try{const value=await readRecoveryContext(scope,groupId,definitionRef);if(!current()||sequence!==epoch.current)return;
   setContext(value);const begin=value.windowRules.currentTime,finish=new Date(Math.max(Date.parse(begin)+3600000,Date.parse(value.windowRules.expiresAfter)+1000)).toISOString();setStart(localInput(begin));setEnd(localInput(finish));
  }catch(e){if(current())setError((e as Error).message);}finally{lock.current=false;if(current())setBusy(false);}
 }
 async function submit(){
  if(blocked||lock.current||!context)return;lock.current=true;setBusy(true);onBusy(true);setError(null);
  try{const receipt=await submitRecoveryCommand(scope,context,{notBefore:new Date(start).toISOString(),expiresAt:new Date(end).toISOString()});if(current())await onConfirmed(receipt);}
  catch(e){if(current())setError((e as Error).message);}finally{lock.current=false;if(current())setBusy(false);onBusy(false);}
 }
 const eligible=context&&(context.runStates.every(r=>r.status==='running'&&r.executorStopped!==true&&r.finishedAt===null)||context.runStates.every(r=>r.status==='failed'&&r.executorStopped===true&&r.finishedAt!==null));
 return <section aria-label="原任务恢复"><h4>恢复原任务</h4><p>继续使用已保存的原采集结果。申请通过后，由执行器在当前权限和有效时间内接续。</p><button type="button" disabled={blocked||busy} onClick={()=>void inspect()}>核对原任务</button>
  {error&&<p role="alert">{error}</p>}
  {context&&<><p>原采集时间：{new Date(context.observation.startedAt).toLocaleString('zh-CN')} 至 {new Date(context.observation.completedAt).toLocaleString('zh-CN')}</p><p>原任务状态：{context.runStates.map(r=>`${r.count} 项${r.status==='running'?'尚未完成':r.status==='failed'?'失败':r.status==='succeeded'?'已完成':'待核对'}${r.executorStopped===true?'（已停止）':'（尚未确认停止）'}`).join('；')}。</p><p>恢复窗口最长 24 小时，开始时间不得早于 {new Date(context.windowRules.notBeforeMinimum).toLocaleString('zh-CN')}，结束时间需晚于 {new Date(context.windowRules.expiresAfter).toLocaleString('zh-CN')}。</p>
   {!eligible&&<p role="status">原任务状态尚不能办理恢复，请先核对执行是否已结束。</p>}
   <label>恢复开始时间（本地时间）<input aria-label="恢复开始时间" type="datetime-local" step="0.001" value={start} disabled={blocked||busy||!eligible} onChange={event=>setStart(event.target.value)}/></label>
   <label>恢复结束时间（本地时间）<input aria-label="恢复结束时间" type="datetime-local" step="0.001" value={end} disabled={blocked||busy||!eligible} onChange={event=>setEnd(event.target.value)}/></label>
   <button type="button" disabled={blocked||busy||!eligible||!start||!end} onClick={()=>void submit()}>提交恢复申请</button>
  </>}
 </section>;
}

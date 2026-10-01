import { useEffect, useRef, useState } from 'react';
import { getAuthRevision, getTenant } from '../../api/tenant';

export function budgetIdentity() { const t=getTenant();return JSON.stringify([t.orgId,t.projectId,t.subject,getAuthRevision()]); }
function slot(ref:unknown) { const t=getTenant();return JSON.stringify([t.orgId,t.projectId,t.subject,ref]); }

/** Shared request exclusion and identity epoch; never authorizes a server action. */
export function useBudgetRequestGuard(onIdentityChange:()=>void) {
 const [busy,setBusy]=useState(false),busyRef=useRef(false),epoch=useRef(0),attempted=useRef(new Set<string>());
 const changedRef=useRef(onIdentityChange);changedRef.current=onIdentityChange;
 function invalidate(){epoch.current++;busyRef.current=false;setBusy(false);}
 useEffect(()=>{
  const changed=()=>{invalidate();changedRef.current();};
  window.addEventListener('aos-auth-updated',changed);window.addEventListener('aos-tenant-updated',changed);
  return()=>{epoch.current++;busyRef.current=false;window.removeEventListener('aos-auth-updated',changed);window.removeEventListener('aos-tenant-updated',changed);};
 },[]);
 return {busy,busyRef,invalidate,
  begin(){if(busyRef.current)return null;busyRef.current=true;setBusy(true);const generation=epoch.current,actor=budgetIdentity();return ()=>generation===epoch.current&&actor===budgetIdentity();},
  finish(current:()=>boolean){if(current()){busyRef.current=false;setBusy(false);}},
  attempted(ref:unknown){return attempted.current.has(slot(ref));},
  markAttempted(ref:unknown){attempted.current.add(slot(ref));},
  checkResult(ref:unknown,status:string){if(status==='not_attempted'&&attempted.current.has(slot(ref)))throw new Error('曾尝试提交但原记录未确认，请核对服务端持久记录，禁止重发');},
 };
}

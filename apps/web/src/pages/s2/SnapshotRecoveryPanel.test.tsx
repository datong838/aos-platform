// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {beforeEach,expect,it,vi} from 'vitest';
const mocks=vi.hoisted(()=>({read:vi.fn(),submit:vi.fn(),scope:{orgId:'org-org',projectId:'dev-project',subject:'operator',auth:1}}));
vi.mock('../../api/snapshotSchedules',()=>({readRecoveryContext:mocks.read,submitRecoveryCommand:mocks.submit,groupScope:()=>mocks.scope}));
import {SnapshotRecoveryPanel} from './SnapshotRecoveryPanel';
(globalThis as {IS_REACT_ACT_ENVIRONMENT?:boolean}).IS_REACT_ACT_ENVIRONMENT=true;
const id='12345678-1234-4234-8234-123456789012',ref={resourceType:'SnapshotScheduleDefinitionRevision',resourceId:'snapshot-schedule-'+id,revision:2,contentHash:'sha256:'+'a'.repeat(64)};
const context={groupId:id,expectedDefinitionRef:ref,observation:{startedAt:'2026-09-15T00:00:00Z',completedAt:'2026-09-15T00:01:00Z'},windowRules:{notBeforeMinimum:'2026-09-15T00:00:00Z',expiresAfter:'2026-09-16T00:00:00Z',currentTime:'2026-09-16T09:00:00Z',maxDurationHours:24},runStates:[{status:'running',executorStopped:false,finishedAt:null,count:12}]};
beforeEach(()=>{vi.clearAllMocks();mocks.scope={orgId:'org-org',projectId:'dev-project',subject:'operator',auth:1};mocks.read.mockResolvedValue(context);});
async function mount(blocked=false){const host=document.createElement('div');document.body.append(host);const root=createRoot(host);const confirmed=vi.fn(),busy=vi.fn();await act(async()=>root.render(<SnapshotRecoveryPanel scope={mocks.scope} groupId={id} definitionRef={ref} blocked={blocked} onConfirmed={confirmed} onBusy={busy}/>));return {host,confirmed,busy,close:async()=>{await act(async()=>root.unmount());host.remove();}};}
const button=(host:HTMLElement,label:string)=>Array.from(host.querySelectorAll('button')).find(b=>b.textContent===label)!;
it('only reads after explicit inspection and prevents duplicate renewal submission',async()=>{
 let reject!:(e:Error)=>void;mocks.submit.mockImplementation(()=>new Promise((_r,fail)=>{reject=fail;}));
 const page=await mount();try{expect(mocks.read).not.toHaveBeenCalled();expect(mocks.submit).not.toHaveBeenCalled();await act(async()=>button(page.host,'核对原任务').click());expect(page.host.textContent).toContain('原采集时间');await act(async()=>{button(page.host,'提交恢复申请').click();button(page.host,'提交恢复申请').click();});expect(mocks.submit).toHaveBeenCalledTimes(1);await act(async()=>reject(new Error('原申请待确认')));expect(page.host.textContent).toContain('原申请待确认');expect(page.confirmed).not.toHaveBeenCalled();}finally{await page.close();}
});
it('does not inspect a blocked or running group',async()=>{
 const page=await mount(true);try{expect(button(page.host,'核对原任务').disabled).toBe(true);expect(mocks.read).not.toHaveBeenCalled();expect(mocks.submit).not.toHaveBeenCalled();}finally{await page.close();}
});
it('drops inspected data after the login scope changes',async()=>{
 let finish!:(v:unknown)=>void;mocks.read.mockImplementation(()=>new Promise(resolve=>{finish=resolve;}));
 const page=await mount();try{await act(async()=>button(page.host,'核对原任务').click());mocks.scope={...mocks.scope,orgId:'dev-org'};await act(async()=>finish(context));expect(page.host.textContent).not.toContain('原采集时间');expect(mocks.submit).not.toHaveBeenCalled();}finally{await page.close();}
});

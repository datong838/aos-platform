// @vitest-environment jsdom
import React,{act} from 'react';
import {createRoot} from 'react-dom/client';
import {beforeEach,expect,it,vi} from 'vitest';
const mocks=vi.hoisted(()=>({list:vi.fn(),options:vi.fn(),submit:vi.fn(),confirm:vi.fn(),read:vi.fn(),pending:vi.fn(),installations:vi.fn(),runtime:vi.fn(),scope:{orgId:'org-org',projectId:'dev-project',subject:'operator',auth:1}}));
vi.mock('../../api/assetControl/client',()=>({assetControlClient:{listInstallations:mocks.installations,getRuntimeInstallation:mocks.runtime}}));
vi.mock('../../api/snapshotSchedules',()=>({groupScope:()=>mocks.scope,listGroups:mocks.list,groupOptions:mocks.options,submitGroupCommand:mocks.submit,confirmGroupCommand:mocks.confirm,readGroup:mocks.read,pendingGroupCommand:mocks.pending}));
import {SnapshotSchedulesPanel} from './SnapshotSchedulesPanel';
(globalThis as {IS_REACT_ACT_ENVIRONMENT?:boolean}).IS_REACT_ACT_ENVIRONMENT=true;
const id='12345678-1234-4234-8234-123456789012';
const policy={resourceType:'SnapshotRelationshipPolicy',resourceId:'policy.json',revision:'1.0.0',contentHash:'sha256:'+'a'.repeat(64)};
const ready={installationId:id,generation:id,status:'ready',missing:[],ambiguous:[],members:Array.from({length:12},(_,i)=>({scheduleId:'s'+i,pipelineId:'p'+i,bindingRef:{revision:1},definitionId:null})),policies:[policy]};
beforeEach(()=>{vi.clearAllMocks();mocks.scope={orgId:'org-org',projectId:'dev-project',subject:'operator',auth:1};mocks.list.mockResolvedValue({items:[],nextCursor:null});mocks.pending.mockReturnValue(null);mocks.installations.mockResolvedValue({items:[{installationId:id,displayName:'栖月汇安装'}],total:1});mocks.runtime.mockResolvedValue({binding:{generation:id}});mocks.options.mockResolvedValue(ready);});
async function renderPanel(){const host=document.createElement('div');document.body.append(host);const root=createRoot(host);await act(async()=>{root.render(<React.StrictMode><SnapshotSchedulesPanel/></React.StrictMode>);});return {host,close:async()=>{await act(async()=>root.unmount());host.remove();}};}
async function selectInstallation(host:HTMLElement){await act(async()=>{const input=host.querySelector('select[aria-label="已安装实例"]') as HTMLSelectElement;input.value=id;input.dispatchEvent(new Event('change',{bubbles:true}));});}
const button=(host:HTMLElement,text:string)=>Array.from(host.querySelectorAll('button')).find(b=>b.textContent===text)!;
it('shows missing sources and prevents saving an incomplete group',async()=>{
 mocks.options.mockResolvedValue({...ready,status:'incomplete',members:[],policies:[],missing:['P01-shop-qyh']});
 const page=await renderPanel();try{await selectInstallation(page.host);expect(page.host.textContent).toContain('来源尚未就绪');expect(button(page.host,'保存为停用配置').disabled).toBe(true);expect(mocks.submit).not.toHaveBeenCalled();}finally{await page.close();}
});
it('blocks a second click while the original configuration submission is pending',async()=>{
 let reject!:(e:Error)=>void;mocks.submit.mockImplementation(()=>new Promise((_resolve,fail)=>{reject=fail;}));
 const page=await renderPanel();try{await selectInstallation(page.host);expect(button(page.host,'保存为停用配置').disabled).toBe(false);await act(async()=>{button(page.host,'保存为停用配置').click();button(page.host,'保存为停用配置').click();});expect(mocks.submit).toHaveBeenCalledTimes(1);expect(mocks.submit.mock.calls[0][2]).toBe('configure');expect(mocks.submit.mock.calls[0][3].expectedRef).toBeNull();await act(async()=>reject(new Error('结果待确认')));}finally{await page.close();}
});
it('restores a pending command without sending it again',async()=>{
 mocks.pending.mockReturnValue({key:'old-original-key',definitionId:id});
 const page=await renderPanel();try{expect(page.host.textContent).toContain('有一项待确认操作');expect(button(page.host,'核对原操作')).toBeDefined();expect(mocks.submit).not.toHaveBeenCalled();expect(mocks.confirm).not.toHaveBeenCalled();expect(button(page.host,'保存为停用配置').disabled).toBe(true);}finally{await page.close();}
});
it('does not render old source choices after switching tenant',async()=>{
 let finish!:(v:unknown)=>void;mocks.options.mockImplementation(()=>new Promise(resolve=>{finish=resolve;}));
 const page=await renderPanel();try{await selectInstallation(page.host);await act(async()=>{mocks.scope={...mocks.scope,orgId:'dev-org'};window.dispatchEvent(new Event('aos-tenant-updated'));});await act(async()=>finish({...ready,status:'incomplete',missing:['old-tenant-secret']}));expect(page.host.textContent).not.toContain('old-tenant-secret');expect(mocks.submit).not.toHaveBeenCalled();}finally{await page.close();}
});

it('shows current state after confirming an older original receipt',async()=>{
 const latest={ref:{revision:3},body:{definitionId:id,installationId:id,generation:id,state:'retired',revision:3,cron:'0 8 * * *',members:ready.members,policyRef:policy}};
 mocks.pending.mockReturnValue({key:'original',definitionId:id});
 mocks.confirm.mockImplementation(async()=>{mocks.pending.mockReturnValue(null);return {body:{definitionId:id,state:'disabled',revision:1}};});
 mocks.read.mockResolvedValue(latest);mocks.list.mockResolvedValue({items:[latest],nextCursor:null});
 const page=await renderPanel();try{await act(async()=>button(page.host,'核对原操作').click());expect(mocks.read).toHaveBeenCalledWith(mocks.scope,id);expect(page.host.textContent).toContain('已退役');expect(page.host.textContent).not.toContain('有一项待确认操作');expect(button(page.host,'启用配置')).toBeUndefined();expect(mocks.submit).not.toHaveBeenCalled();}finally{await page.close();}
});

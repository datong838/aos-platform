// @vitest-environment jsdom
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { expect,it,vi } from 'vitest';
const mocks=vi.hoisted(() => ({recover:vi.fn(),reload:vi.fn()}));
vi.mock('../../api/scheduleRecovery',()=>({recoverScheduledRun:mocks.recover}));
vi.mock('../../api/tenant',()=>({getTenant:()=>({orgId:'org-org',projectId:'dev-project',subject:'user',roles:['data-owner']})}));
vi.mock('./shared',()=>({
 S2Chrome:({children}:{children:React.ReactNode})=>children,
 PipelineWorkflowStepper:()=>null,
 useJsonGet:(path:string|null)=>({loading:false,err:null,reload:mocks.reload,data:!path?undefined:path.includes('/runs')?{items:[{id:'run',status:'failed',finishedAt:'at',recovery:{candidate:true,reason:'ready'}}]}:path.includes('/pipelines')?{items:[]}:{items:[{id:'s1',name:'计划一',enabled:true,cron:'0 * * * *',pipelineId:'p'},{id:'s2',name:'计划二',enabled:true,cron:'0 * * * *',pipelineId:'p'}]}})
}));
import { SchedulesPage } from './dataSchedules';
(globalThis as {IS_REACT_ACT_ENVIRONMENT?:boolean}).IS_REACT_ACT_ENVIRONMENT=true;

it('blocks duplicate recovery and ignores results after selecting another schedule',async()=>{
 let finish!:(value:{status:string})=>void;
 mocks.recover.mockImplementation(()=>new Promise(resolve=>{finish=resolve;}));
 const host=document.createElement('div');document.body.append(host);const root=createRoot(host);
 const buttons=(text:string)=>Array.from(host.querySelectorAll('button')).filter(b=>b.textContent===text);
 try {
  await act(async()=>{root.render(<MemoryRouter><SchedulesPage/></MemoryRouter>);});
  await act(async()=>{buttons('编辑')[0].click();});
  await act(async()=>{const button=buttons('恢复原运行')[0];button.click();button.click();});
  expect(mocks.recover).toHaveBeenCalledTimes(1);
  expect(mocks.recover).toHaveBeenCalledWith('s1','run','at');
  expect(buttons('立即真实同步')[0].disabled).toBe(true);
  await act(async()=>{buttons('编辑')[1].click();});
  await act(async()=>{finish({status:'succeeded'});await Promise.resolve();});
  expect(host.textContent).not.toContain('原运行已恢复完成');
  expect(buttons('立即真实同步')[0].disabled).toBe(false);
 } finally { await act(async()=>root.unmount());host.remove(); }
});

import { act, createElement } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { DataPage } from './DataPage';
const api=vi.hoisted(()=>({apiGet:vi.fn(),apiPost:vi.fn()}));
vi.mock('../api/client',()=>api);
vi.mock('../components/PageChrome',()=>({PageChrome:({children}:any)=>children}));
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let host:HTMLDivElement, root:Root;
beforeEach(()=>{host=document.createElement('div');document.body.append(host);root=createRoot(host);vi.clearAllMocks();});
afterEach(()=>{act(()=>root.unmount());host.remove();});
async function click(text:string){const b=Array.from(host.querySelectorAll('button')).find(b=>b.textContent?.trim()===text);if(!b)throw Error(`button missing: ${text}`);await act(async()=>b.click());}
async function input(text:string,value:string){const label=Array.from(host.querySelectorAll('label')).find(l=>l.textContent?.trim().startsWith(text));const el=label?.querySelector('input');if(!el)throw Error(`input missing: ${text}`);await act(async()=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!.call(el,value);el.dispatchEvent(new Event('input',{bubbles:true}));});}
it.each(['success','readback-drift'])('saved source interaction: %s',async(mode)=>{
 const revision='12345678-1234-1234-1234-123456789012';
 let saved:any=null;let resolveProbe!:(x:any)=>void;
 const events:string[]=[];
 api.apiGet.mockImplementation(async(path:string)=>{
  if(path==='/v1/connector-plugins')return {items:[{id:'jdbc-mysql-ssh',name:'MySQL SSH',installed:true,runtime:'live'}]};
  if(path==='/v1/sources'){if(saved)events.push('readback');return {items:saved?[mode==='readback-drift'?{...saved,configurationRevision:'drift'}:saved]:[]};}
  return {items:[]};
 });
 api.apiPost.mockImplementation((path:string,body:any)=>{
  if(path==='/v1/sources'){events.push('save');expect(body.config.sshPort).toBe(2222);expect(body.config.dbPort).toBe(3306);expect(body.config).not.toHaveProperty('apiKey');saved={id:body.id,runtimeMode:'direct',configurationRevision:revision};return Promise.resolve(saved);}
  events.push('probe');expect(body).toEqual({expectedConfigurationRevision:revision});return new Promise(resolve=>{resolveProbe=resolve;});
 });
 await act(async()=>root.render(createElement(MemoryRouter,{initialEntries:['/data?create=1&connector=jdbc-mysql-ssh']},createElement(DataPage))));
 await click('下一步 →');
 const direct=Array.from(host.querySelectorAll('button')).find(b=>b.textContent?.includes('直接连接'))!;
 await act(async()=>direct.click());
 await click('下一步 →');
 await input('SSH 主机','example.invalid');await input('SSH 端口','2222');await input('SSH 用户名','reader');await input('SSH 密码','synthetic-ssh');
 await input('主机地址','127.0.0.1');await input('端口','3306');await input('数据库名','shop');await input('用户名','reader');
 await click('下一步 →');await input('密码','synthetic-db');await click('创建数据源');
 if(mode==='readback-drift'){
  expect(events).toEqual(['save','readback']);
  expect(host.querySelector('fieldset')?.disabled).toBe(false);
  expect(host.textContent).toContain('保存或测试未确认成功');
  return;
 }
 expect(events).toEqual(['save','readback','probe']);
 expect(host.querySelector('fieldset')?.disabled).toBe(true);
 await act(async()=>resolveProbe({ok:true,sourceId:saved.id,configurationRevision:revision,tables:[{name:'ns_goods',type:'BASE TABLE'}],truncated:false,latencyMs:10}));
 expect(host.textContent).toContain('ns_goods');expect(host.textContent).toContain('尚未执行数据同步');
 await click('上一步');await input('数据库名','other');
 expect(host.textContent).not.toContain('ns_goods');
});

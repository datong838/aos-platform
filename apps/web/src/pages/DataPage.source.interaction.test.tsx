import { act, createElement } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { DataPage } from './DataPage';
const api=vi.hoisted(()=>({apiGet:vi.fn(),apiGetAuthoritative:vi.fn(),apiPost:vi.fn(),apiPostUnqueued:vi.fn()}));
const tenant=vi.hoisted(()=>({current:{orgId:'org-org',projectId:'dev-project'}}));
vi.mock('../api/client',()=>api);
vi.mock('../api/tenant',()=>({getTenant:()=>tenant.current}));
vi.mock('../components/PageChrome',()=>({PageChrome:({children}:any)=>children}));
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let host:HTMLDivElement, root:Root;
beforeEach(()=>{tenant.current={orgId:'org-org',projectId:'dev-project'};localStorage.clear();host=document.createElement('div');document.body.append(host);root=createRoot(host);vi.clearAllMocks();});
afterEach(()=>{act(()=>root.unmount());host.remove();localStorage.clear();});
async function click(text:string){const b=Array.from(host.querySelectorAll('button')).find(b=>b.textContent?.trim()===text);if(!b)throw Error(`button missing: ${text}`);await act(async()=>b.click());}
async function input(text:string,value:string){const label=Array.from(host.querySelectorAll('label')).find(l=>l.textContent?.trim().startsWith(text));const el=label?.querySelector('input');if(!el)throw Error(`input missing: ${text}`);await act(async()=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!.call(el,value);el.dispatchEvent(new Event('input',{bubbles:true}));});}
it.each(['success','readback-drift'])('saved source interaction: %s',async(mode)=>{
 const revision='12345678-1234-1234-1234-123456789012';
 let saved:any=null;
 const events:string[]=[];
 api.apiGet.mockImplementation(async(path:string)=>{
  if(path==='/v1/connector-plugins')return {items:[{id:'jdbc-mysql-ssh',name:'MySQL SSH',installed:true,runtime:'live'}]};
  if(path==='/v1/sources'){if(saved)events.push('readback');return {items:saved?[mode==='readback-drift'?{...saved,configurationRevision:'drift'}:saved]:[]};}
  return {items:[]};
 });
 api.apiGetAuthoritative.mockImplementation(async(path:string)=>{
  if(path.includes('/registration-receipt?key=')){
   events.push('receipt');return {sourceId:saved.id,configurationRevision:revision,responseMetadata:saved};
  }
  expect(path).toBe('/v1/sources');events.push(saved?'readback':'preflight');
  return {items:saved?[mode==='readback-drift'?{...saved,configurationRevision:'drift'}:saved]:[]};
 });
 api.apiPostUnqueued.mockImplementation((path:string,body:any,headers:any)=>{
  expect(headers['Idempotency-Key']).toMatch(/^[0-9a-f-]{36}$/);
  if(path==='/v1/sources'){events.push('save');expect(body.config.sshPort).toBe(2222);expect(body.config.dbPort).toBe(3306);expect(body.config).not.toHaveProperty('apiKey');saved={id:body.id,runtimeMode:'direct',configurationRevision:revision};return Promise.resolve(saved);}
  throw Error('unexpected write');
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
  expect(events).toEqual(['preflight','save','readback']);
  expect(host.querySelector('fieldset')?.disabled).toBe(true);
  expect(host.textContent).toContain('登记结果未核清');
  const marker=localStorage.getItem('aos:source-create:pending:org-org:dev-project')||'';
  expect(marker).toContain(saved.id);expect(marker).not.toContain('synthetic-ssh');expect(marker).not.toContain('synthetic-db');
  await click('只读对账登记状态');expect(api.apiPostUnqueued).toHaveBeenCalledTimes(1);
  return;
 }
 expect(events).toEqual(['preflight','save','readback','receipt','readback']);
 expect(api.apiPost).not.toHaveBeenCalledWith(expect.stringContaining('/test'),expect.anything());
 expect(localStorage.getItem('aos:source-create:pending:org-org:dev-project')).toBeNull();
 expect(host.textContent).toContain('未测试连接，未执行同步');
});

it('reconciles an original-key receipt after reopening without resending', async () => {
 const key='aos:source-create:pending:org-org:dev-project';
 localStorage.setItem(key, JSON.stringify({id:'unknown-source',runtimeMode:'direct',expectedConfigurationRevision:null,key:'original-key'}));
 api.apiGet.mockImplementation(async(path:string) => path==='/v1/connector-plugins' ? {items:[]} : {items:[]});
 api.apiGetAuthoritative.mockImplementation(async(path:string) => path.includes('/registration-receipt?key=')
  ? {sourceId:'unknown-source',configurationRevision:'12345678-1234-1234-1234-123456789012',responseMetadata:{id:'unknown-source',runtimeMode:'direct',configurationRevision:'12345678-1234-1234-1234-123456789012'}}
  : {items:[{id:'unknown-source',runtimeMode:'direct',configurationRevision:'12345678-1234-1234-1234-123456789012'}]});
 await act(async()=>root.render(createElement(MemoryRouter,{initialEntries:['/data?create=1']},createElement(DataPage))));
 expect(host.querySelector('fieldset')?.disabled).toBe(true);
 await click('只读对账登记状态');
 expect(host.textContent).toContain('已按原幂等键核清');
 expect(localStorage.getItem(key)).toBeNull();
 expect(api.apiPostUnqueued).not.toHaveBeenCalled();
});

it('keeps unknown registration frozen when its original receipt is absent', async () => {
 const key='aos:source-create:pending:org-org:dev-project';
 localStorage.setItem(key,JSON.stringify({id:'unknown-source',runtimeMode:'direct',expectedConfigurationRevision:null,key:'original-key'}));
 api.apiGet.mockResolvedValue({items:[]});
 api.apiGetAuthoritative.mockRejectedValue(new Error('404'));
 await act(async()=>root.render(createElement(MemoryRouter,{initialEntries:['/data?create=1']},createElement(DataPage))));
 await click('只读对账登记状态');
 expect(localStorage.getItem(key)).not.toBeNull();
 expect(host.querySelector('fieldset')?.disabled).toBe(true);
 expect(api.apiPostUnqueued).not.toHaveBeenCalled();
});

it('loads the matching pending marker when tenant changes without clearing the original', async () => {
 const original='aos:source-create:pending:org-org:dev-project';
 const switched='aos:source-create:pending:dev-org:dev-project';
 localStorage.setItem(original,JSON.stringify({id:'source-a',runtimeMode:'direct',expectedConfigurationRevision:null}));
 localStorage.setItem(switched,JSON.stringify({id:'source-b',runtimeMode:'direct',expectedConfigurationRevision:null}));
 api.apiGet.mockResolvedValue({items:[]});
 await act(async()=>root.render(createElement(MemoryRouter,{initialEntries:['/data?create=1']},createElement(DataPage))));
 expect(host.textContent).toContain('source-a');
 await act(async()=>{tenant.current={orgId:'dev-org',projectId:'dev-project'};window.dispatchEvent(new Event('aos-tenant-updated'));});
 expect(host.textContent).toContain('source-b');
 expect(host.querySelector('fieldset')?.disabled).toBe(true);
 expect(localStorage.getItem(original)).not.toBeNull();
});

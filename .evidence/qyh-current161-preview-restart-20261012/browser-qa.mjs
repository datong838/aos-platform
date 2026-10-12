import playwright from '/Users/ddt/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.js';
import fs from 'node:fs';
import path from 'node:path';
const out=path.dirname(new URL(import.meta.url).pathname);
if(fs.existsSync(path.join(out,'browser-readback.json'))) throw new Error('Reconcile existing evidence');
const browser=await playwright.chromium.connectOverCDP('http://127.0.0.1:9244');
const page=await browser.contexts()[0].newPage();
const errors=[],mutations=[],rows=[];
page.on('pageerror',e=>errors.push(e.name));
page.on('request',r=>{if(new URL(r.url()).port==='18434'&&!['GET','HEAD','OPTIONS'].includes(r.method()))mutations.push({method:r.method(),path:new URL(r.url()).pathname});});
try{
 for(const route of ['cockpit','content-campaign','operations','creator-growth','media-studio','analyst','price-governance','customer']){
  const response=await page.goto('http://127.0.0.1:18434/workshop/'+route);
  await page.getByText('当前工作台入口不可用',{exact:true}).waitFor({timeout:30000});
  await page.getByText('栖月汇商贸有限公司',{exact:false}).first().waitFor({timeout:30000});
  const refresh=page.getByRole('button',{name:'重新读取目录',exact:true});
  if(await refresh.count()>0){await refresh.last().click();await page.getByText('当前工作台入口不可用',{exact:true}).waitFor();}
  const api=await page.request.get('http://127.0.0.1:18434/api/v1/runtime-workshop/modules',{headers:{Authorization:'Bearer dev','X-Org-Id':'org-org','X-Project-Id':'dev-project'}});
  const catalog=await api.json();
  if(catalog.tenant?.orgId!=='org-org'||catalog.tenant?.projectId!=='dev-project'||catalog.count!==0)throw new Error('Unexpected actual catalog scope/state');
  await page.screenshot({path:path.join(out,route+'.png'),fullPage:true});
  rows.push({route,documentStatus:response.status(),qyhNameVisible:true,catalogStatus:api.status(),catalogTenant:catalog.tenant,catalogCount:catalog.count,actualState:'UNAVAILABLE_DISABLED_OR_FENCED_INSTALLATIONS',catalogRefreshReadOnly:true});
 }
 fs.writeFileSync(path.join(out,'browser-readback.json'),JSON.stringify({rows,pageErrorTypes:errors,mutationRequests:mutations,mockedResponses:false,requestInterception:false,eightWorkbenchesFunctionallyAccepted:false,tabRetained:true},null,2),{flag:'wx'});
 console.log(JSON.stringify({routes:rows.length,pageErrors:errors.length,mutationRequests:mutations.length,eightWorkbenchesFunctionallyAccepted:false,tabRetained:true}));
}finally{await browser.close();}

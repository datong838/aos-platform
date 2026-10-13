import pw from '/Users/ddt/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.js';
import fs from 'node:fs';import path from 'node:path';
const task=path.dirname(new URL(import.meta.url).pathname);
const browser=await pw.chromium.connectOverCDP('http://127.0.0.1:9244');
const context=browser.contexts()[0];
const routes=JSON.parse(fs.readFileSync(path.join(task,'native-readonly-result.json'),'utf8')).modules.items;
const candidates=[];
for(const p of context.pages().filter(p=>p.url()==='http://127.0.0.1:18434/workshop/customer')){
 if(await p.locator('.ecommerce-workshop-shell[data-module-id="ecommerce.customer"]').count()===1)candidates.push(p);
}
if(candidates.length!==1)throw new Error('Cannot uniquely reconcile retained owned current eight-directory page');
const page=candidates[0];const cdp=await context.newCDPSession(page);const info=await cdp.send('Target.getTargetInfo');
fs.writeFileSync(path.join(task,'browser-settled-intent.json'),JSON.stringify({ownedTargetId:info.targetInfo.targetId,identification:'unique retained current original customer shell following successful credential attempt',credentialResubmission:false},null,2),{flag:'wx'});
const errors=[];page.on('pageerror',e=>errors.push(e.name));const reads=[];
page.on('response',r=>{const u=new URL(r.url());if(u.pathname.startsWith('/api/v1/ecommerce-workshop/'))reads.push({path:u.pathname,status:r.status()});});
const results=[];
for(const module of routes){
 await page.evaluate(route=>{history.pushState({},'',route);window.dispatchEvent(new PopStateEvent('popstate'));},module.route);
 const shell=page.locator(`.ecommerce-workshop-shell[data-module-id="${module.moduleId}"]`);
 await shell.waitFor({timeout:20000});
 const klass=module.moduleId.slice('ecommerce.'.length)+'-page';
 await shell.locator(`.${klass}`).waitFor({timeout:20000});
 await page.waitForFunction(klass=>{const el=document.querySelector('.'+klass);return el&&!el.querySelector('.is-loading');},klass,{timeout:30000});
 const body=await shell.locator(`.${klass}`).innerText();
 await page.screenshot({path:path.join(task,`settled-${module.moduleId}.png`),fullPage:true});
 const menus=await page.locator(`a[href="${module.route}"]`).count();
 const blocked=await shell.locator('.is-failed,.is-forbidden,.is-blocked,.is-unknown').count();
 results.push({moduleId:module.moduleId,route:module.route,originalComponent:klass,menuCount:menus,settled:true,contentCharacterCount:body.length,businessReadModelUnverified:blocked>0,visibleStateText:body.slice(0,400)});
}
if(errors.length||results.some(r=>!r.settled||r.menuCount<1))throw new Error('Settled original eight view acceptance incomplete');
fs.writeFileSync(path.join(task,'browser-eight-settled-result.json'),JSON.stringify({outcome:'ORIGINAL_EIGHT_INSTALLED_READONLY_MENUS_AND_SETTLED_COMPONENTS_ACCEPTED',ownedTargetId:info.targetInfo.targetId,credentialReplay:false,initialScreenshotsWereLoading:true,initialResultSupersededForSettledAcceptance:true,modules:results,httpReads:reads,pageErrors:errors,businessDataReady:false,businessFirstChainAccepted:false,externalSourceRead:false,tabRetained:true},null,2),{flag:'wx'});
console.log('Eight original component roots settled and visible; business read models remain explicitly unverified; original owned tab retained.');
process.exit(0);

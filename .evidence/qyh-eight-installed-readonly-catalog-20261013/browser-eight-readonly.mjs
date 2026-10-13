import pw from '/Users/ddt/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.js';
import fs from 'node:fs';
import path from 'node:path';
const task=path.dirname(new URL(import.meta.url).pathname);
const intent=path.join(task,'browser-eight-intent.json');
if(fs.existsSync(intent))throw new Error('Existing browser attempt: reconcile owned page before retry');
const evidence=JSON.parse(fs.readFileSync(path.join(task,'native-readonly-result.json'),'utf8'));
const modules=evidence.modules.items;
const browser=await pw.chromium.connectOverCDP('http://127.0.0.1:9244');
const page=await browser.contexts()[0].newPage();
const failures=[];page.on('pageerror',error=>failures.push(error.name));
try{
 await page.goto('http://127.0.0.1:18434/workshop/customer',{waitUntil:'domcontentloaded'});
 await page.getByLabel('登录名',{exact:true}).waitFor({timeout:20000});
 fs.writeFileSync(intent,JSON.stringify({origin:'http://127.0.0.1:18434',dedicatedPort:9244,newTaskTab:true,credentialSubmissionOnce:true,operation:'authorized original login and readonly eight views'},null,2),{flag:'wx'});
 const secret=JSON.parse(fs.readFileSync('/Users/ddt/.aos-local-identities/qyh-20261013/user-password-input.json','utf8'));
 await page.getByLabel('登录名',{exact:true}).fill(secret.username);
 await page.getByLabel('密码',{exact:true}).fill(secret.password);
 const mePromise=page.waitForResponse(r=>r.url().endsWith('/v1/me')&&r.request().method()==='GET'&&r.status()===200,{timeout:30000});
 const catalogPromise=page.waitForResponse(r=>r.url().endsWith('/v1/ecommerce-workshop/installed-readonly-modules')&&r.request().method()==='GET',{timeout:30000});
 await page.getByRole('button',{name:'登录',exact:true}).click();
 const me=await (await mePromise).json();
 if(me.subject!=='6f31cfdc-a26c-4f1f-ad6b-95a8559cc657'||me.orgId!=='org-org'||me.projectId!=='dev-project'||me.tokenKind!=='oidc')throw new Error('Canonical persisted human identity mismatch');
 const response=await catalogPromise;const actual=await response.json();
 if(response.status()!==200||actual.count!==8||actual.items.some(x=>x.readiness!=='disabled'||x.installationRef.installationId!=='ab2fd72f-d81c-400d-bbbc-e1589a159d6b'))throw new Error('Current signed readonly catalog mismatch');
 const results=[];
 for(const module of modules){
  await page.evaluate(route=>{history.pushState({},'',route);window.dispatchEvent(new PopStateEvent('popstate'));},module.route);
  await page.locator(`[data-module-id="${module.moduleId}"]`).first().waitFor({timeout:20000});
  const menuCount=await page.locator(`a[href="${module.route}"]`).count();
  const shellCount=await page.locator(`[data-module-id="${module.moduleId}"]`).count();
  await page.screenshot({path:path.join(task,`actual-${module.moduleId}.png`),fullPage:true});
  results.push({moduleId:module.moduleId,route:module.route,menuCount,originalShellVisible:shellCount>0});
 }
 if(results.some(x=>x.menuCount===0)||failures.length)throw new Error('Eight original menu/page acceptance incomplete');
 fs.writeFileSync(path.join(task,'browser-eight-result.json'),JSON.stringify({outcome:'ACTUAL_CURRENT_SIGNED_EIGHT_ORIGINAL_MENUS_AND_READONLY_PAGES_ACCEPTED',tenant:{orgId:me.orgId,orgName:me.orgName,projectId:me.projectId},actualLoginOidc:true,agentAuthorizedCredentialTest:true,interactiveHumanLoginObserved:false,modules:results,pageErrors:failures,requestInterception:false,mockedResponses:false,credentialsRecorded:false,businessFirstChainAccepted:false,runtimeAuthorized:false,tabRetained:true},null,2),{flag:'wx'});
 console.log('Actual OIDC eight menus and original readonly pages accepted; task-owned tab retained.');
}catch(error){
 fs.writeFileSync(path.join(task,'browser-eight-failure.json'),JSON.stringify({errorClass:error?.constructor?.name||'Error',message:String(error?.message||'Failure').slice(0,220),ownedPath:new URL(page.url()).pathname,credentialsRecorded:false,doNotReplayCredentialSubmission:true},null,2),{flag:'wx'});
 console.log('Eight-page acceptance failed; owned tab and sanitized evidence retained.');process.exitCode=1;
}
process.exit(process.exitCode||0);

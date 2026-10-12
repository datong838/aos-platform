import pw from '/Users/ddt/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.js';
import fs from 'node:fs';
const out='/Users/ddt/work/projects/ai_agent/aos-platform/.evidence/qyh-managed-person-profile-coldstart-20261013';
if(fs.existsSync(out+'/browser-intent.json')) throw new Error('Existing attempt: reconcile owned page; no credential replay.');
const browser=await pw.chromium.connectOverCDP('http://127.0.0.1:9244');
const page=await browser.contexts()[0].newPage();
try {
  await page.goto('http://127.0.0.1:18434/settings/profile',{waitUntil:'domcontentloaded'});
  await page.getByLabel('登录名',{exact:true}).waitFor({timeout:20000});
  fs.writeFileSync(out+'/browser-intent.json',JSON.stringify({origin:'http://127.0.0.1:18434',path:'/settings/profile',dedicatedPort:9244,newTaskTab:true,singleCredentialSubmission:true},null,2));
  const secret=JSON.parse(fs.readFileSync('/Users/ddt/.aos-local-identities/qyh-20261013/user-password-input.json','utf8'));
  await page.getByLabel('登录名',{exact:true}).fill(secret.username);
  await page.getByLabel('密码',{exact:true}).fill(secret.password);
  const mePromise=page.waitForResponse(r=>r.url().endsWith('/v1/me')&&r.request().method()==='GET'&&r.status()===200,{timeout:20000});
  await page.getByRole('button',{name:'登录',exact:true}).click();
  const response=await mePromise;const me=await response.json();
  if(response.status()!==200||me.subject!=='6f31cfdc-a26c-4f1f-ad6b-95a8559cc657'||me.displayName!=='datong838'||me.orgId!=='org-org'||me.projectId!=='dev-project'||me.tokenKind!=='oidc') throw new Error('Canonical persisted profile mismatch');
  await page.getByRole('heading',{name:'AOS 登录',exact:true}).waitFor({state:'hidden'});
  await page.waitForFunction(()=>Array.from(document.querySelectorAll('input:not([type="password"])')).some(input=>input.value==='datong838'),undefined,{timeout:20000});
  const profileVisible=await page.locator('input').evaluateAll(inputs=>inputs.some(input=>input.value==='datong838'));
  if(!profileVisible) throw new Error('Persisted display name not visible on profile form');
  await page.screenshot({path:out+'/actual-profile.png',fullPage:true});
  fs.writeFileSync(out+'/browser-result.json',JSON.stringify({outcome:'ACTUAL_MANAGED_COLDSTART_PROFILE_AND_BROWSER_GREEN',me:{subject:me.subject,displayName:me.displayName,orgId:me.orgId,orgName:me.orgName,projectId:me.projectId,tokenKind:me.tokenKind},visibleProfileName:true,browserKeptOpen:true,agentAuthorizedCredentialTest:true,interactiveHumanLoginObserved:false,tokenOrPasswordRecorded:false,eightPagesAccepted:false},null,2));
  console.log('Actual persisted human displayName datong838 accepted in original me and visible profile page; browser retained.');
} catch(error) {
  fs.writeFileSync(out+'/browser-failure.json',JSON.stringify({errorClass:error?.constructor?.name||'Error',path:page.url(),noAutomaticResend:true,credentialsEmitted:false},null,2));
  console.log('Browser acceptance failed; sanitized exact-page evidence recorded.');process.exitCode=1;
}
process.exit(process.exitCode||0);

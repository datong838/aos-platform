import pw from '/Users/ddt/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.js';
import fs from 'node:fs';
const base = '/Users/ddt/work/projects/ai_agent/aos-platform/.evidence/qyh-full-system-restoration-20261011';
const intent = base + '/browser-human-login-intent-20261013.json';
if (fs.existsSync(intent)) throw new Error('Existing browser attempt: reconcile exact page only.');
const browser = await pw.chromium.connectOverCDP('http://127.0.0.1:9244');
const context = browser.contexts()[0];
const page = await context.newPage();
try {
  await page.goto('http://127.0.0.1:18434/', { waitUntil: 'domcontentloaded' });
  await page.getByRole('heading', { name: 'AOS 登录', exact: true }).waitFor({ timeout: 20000 });
  await page.getByLabel('登录名', { exact: true }).waitFor();
  fs.writeFileSync(intent, JSON.stringify({ origin: 'http://127.0.0.1:18434', dedicatedPort: 9244, newTaskPage: true, originalLoginFormVisible: true, oneCredentialSubmission: true }, null, 2));
  const secret = JSON.parse(fs.readFileSync('/Users/ddt/.aos-local-identities/qyh-20261013/user-password-input.json', 'utf8'));
  await page.getByLabel('登录名', { exact: true }).fill(secret.username);
  await page.getByLabel('密码', { exact: true }).fill(secret.password);
  const mePromise = page.waitForResponse(response => response.url().endsWith('/v1/me') && response.request().method() === 'GET', { timeout: 20000 });
  await page.getByRole('button', { name: '登录', exact: true }).click();
  const response = await mePromise;
  const me = await response.json();
  if (response.status() !== 200 || me.subject !== '6f31cfdc-a26c-4f1f-ad6b-95a8559cc657' || me.orgId !== 'org-org' || me.projectId !== 'dev-project' || me.tokenKind !== 'oidc' || !me.roles.includes('admin')) throw new Error('Canonical identity check failed');
  await page.getByRole('heading', { name: 'AOS 登录', exact: true }).waitFor({ state: 'hidden', timeout: 20000 });
  await page.screenshot({ path: base + '/actual-browser-human-login-20261013.png', fullPage: true });
  fs.writeFileSync(base + '/actual-browser-human-login-20261013.json', JSON.stringify({ outcome: 'ACTUAL_AOS_WEB_HUMAN_LOGIN_QYH_SCOPE_GREEN', agentAuthorizedCredentialTest: true, interactiveHumanLoginObserved: false, me: { subject: me.subject, orgId: me.orgId, orgName: me.orgName, projectId: me.projectId, workspaceName: me.workspaceName, roles: me.roles, tokenKind: me.tokenKind, displayName: me.displayName }, browserKeptOpen: true, tokenOrPasswordRecorded: false, eightWorkbenchesAccepted: false, remainingProfileHydration: me.displayName !== 'datong838' }, null, 2));
  console.log('Actual AOS browser login and canonical Qyh administrator scope verified; tab retained.');
} catch (error) {
  fs.writeFileSync(base + '/browser-human-login-failure-20261013.json', JSON.stringify({ errorClass: error?.constructor?.name || 'Error', pageUrl: page.url(), outcome: 'FAILED_RECONCILE_OWN_BROWSER_ATTEMPT', credentialsEmitted: false }, null, 2));
  console.log('Browser attempt failed; sanitized exact-page failure recorded; no automatic resend.');
  process.exitCode = 1;
}

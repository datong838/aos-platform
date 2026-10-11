import playwright from '/Users/ddt/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.js';
const { chromium } = playwright;
import fs from 'node:fs';
import path from 'node:path';
const task = path.dirname(new URL(import.meta.url).pathname);
const suffix = process.argv[2] ?? '';
if (!/^(|-r[0-9]+)$/.test(suffix)) throw new Error('Invalid evidence suffix');
const browser = await chromium.connectOverCDP('http://127.0.0.1:9244');
const page = await browser.contexts()[0].newPage();
const origin = 'http://127.0.0.1:18434';
const failures = [];
page.on('pageerror', error => failures.push(error.name));
try {
  await page.goto(origin + '/org/membership');
  await page.getByText('栖月汇商贸有限公司', { exact: false }).first().waitFor({ timeout: 30000 });
  await page.screenshot({ path: path.join(task, `management-org-restored${suffix}.png`), fullPage: true });
  const actual = await page.evaluate(async () => {
    const headers = { Authorization: 'Bearer dev', 'X-Org-Id': 'org-org', 'X-Project-Id': 'dev-project' };
    const get = async (route, extra = {}) => {
      const r = await fetch('/api' + route, { headers: { ...headers, ...extra }, cache: 'no-store' });
      const data = await r.json();
      return { status: r.status, data };
    };
    const me = await get('/v1/me');
    const installations = await get('/v1/bundle-installations?limit=5&offset=0');
    const runtime = await get('/v1/bundle-runtime-installations/407059df-6f1f-4927-acd7-8e388692838e');
    const canary = await get('/v1/bundle-runtime-installations/407059df-6f1f-4927-acd7-8e388692838e', { 'X-Org-Id': 'dev-org' });
    const mutation = await fetch('/api/v1/auth/token', { method: 'POST', headers: { ...headers, 'Content-Type': 'application/json' }, body: '{}' });
    return { me: { status: me.status, orgId: me.data.orgId, orgName: me.data.orgName, projectId: me.data.projectId },
      installations: { status: installations.status, total: installations.data.total },
      runtime: { status: runtime.status, effectiveState: runtime.data.effectiveState, allowedActions: runtime.data.allowedActions },
      canary: { status: canary.status, code: canary.data.code }, mutation: { status: mutation.status } };
  });
  if (actual.me.orgName !== '栖月汇商贸有限公司' || actual.me.orgId !== 'org-org'
      || actual.me.projectId !== 'dev-project' || actual.installations.total !== 135
      || actual.runtime.effectiveState !== 'needs_attention' || actual.runtime.allowedActions.length !== 0
      || actual.canary.status !== 404 || actual.mutation.status !== 405) throw new Error('Restored management acceptance failed');
  await page.goto(origin + '/apollo/assets');
  await page.getByText('安装管理', { exact: false }).first().waitFor({ timeout: 30000 });
  await page.screenshot({ path: path.join(task, `management-installations-restored${suffix}.png`), fullPage: true });
  const report = { outcome: 'RESTORED_REAL_MANAGEMENT_BROWSER_ACCEPTED', origin, actual,
    pageErrorTypes: failures, requestInterception: false, mockedResponses: false,
    runtimeAuthorized: false, formalIdentityVerified: false, eightPagesAccepted: false, tabRetained: true };
  fs.writeFileSync(path.join(task, `management-browser-qa${suffix}.json`), JSON.stringify(report, null, 2), { flag: 'wx' });
  console.log(JSON.stringify(report));
} finally { await browser.close(); }

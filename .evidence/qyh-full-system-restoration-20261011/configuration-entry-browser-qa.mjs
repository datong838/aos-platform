import playwright from '/Users/ddt/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.js';
import fs from 'node:fs';
import path from 'node:path';
const task = path.dirname(new URL(import.meta.url).pathname);
const suffix = process.argv[2] ?? '';
if (!/^(|-r[0-9]+)$/.test(suffix)) throw new Error('Invalid evidence suffix');
const output = path.join(task, `configuration-entry-browser-qa${suffix}.json`);
if (fs.existsSync(output)) throw new Error('Existing result: reconcile only');
const browser = await playwright.chromium.connectOverCDP('http://127.0.0.1:9244');
const page = await browser.contexts()[0].newPage();
const errors = [];
page.on('pageerror', error => errors.push(error.name));
const iid = '407059df-6f1f-4927-acd7-8e388692838e';
try {
  await page.goto('http://127.0.0.1:18434/apollo/assets');
  await page.getByText('资产 Registry', { exact: true }).first().waitFor({ timeout: 30000 });
  await page.getByRole('tab', { name: '安装管理', exact: true }).click({ timeout: 30000 });
  const list = page.getByRole('region', { name: '安装列表', exact: true });
  await list.getByRole('table').waitFor({ timeout: 30000 });
  const row = list.getByRole('row').filter({ hasText: iid });
  for (let step = 0; step < 6 && await row.count() === 0; step++) {
    const next = list.getByRole('button', { name: '下一页', exact: true });
    if (await next.isDisabled()) break;
    const response = page.waitForResponse(r => r.url().includes('/v1/bundle-installations?') && r.status() === 200);
    await next.click();
    await response;
    await page.getByText('正在刷新安装列表…', { exact: true }).waitFor({ state: 'hidden', timeout: 30000 });
  }
  if (await row.count() !== 1) throw new Error('Expected preserved installation not uniquely visible');
  await row.getByRole('button', { name: '查看事件', exact: true }).click();
  const candidates = page.getByRole('region', { name: '当前配置权威候选', exact: true });
  await candidates.getByText('预算策略：缺少当前候选', { exact: false }).waitFor({ timeout: 30000 });
  const stage = page.getByRole('region', { name: '登记运行配置', exact: true });
  await stage.getByText('配置登记服务尚未启用，可查看来源。', { exact: true }).waitFor({ timeout: 30000 });
  const stageDisabled = await stage.getByRole('button', { name: '登记所选配置', exact: true }).isDisabled();
  if (!stageDisabled) throw new Error('Configuration submission unexpectedly enabled');
  await candidates.screenshot({ path: path.join(task, `configuration-entry-current-gates${suffix}.png`) });
  await stage.screenshot({ path: path.join(task, `configuration-entry-stage-gate${suffix}.png`) });
  const report = { outcome: 'RESTORED_CONFIGURATION_ENTRY_BROWSER_ACCEPTED', installationId: iid,
    actualBudgetPolicyMissing: true, currentSourcesVisible: true, stageDisabled,
    pageErrorTypes: errors, mutationClicks: 0, mockedResponses: false, requestInterception: false,
    formalIdentityVerified: false, runtimeAuthorized: false, eightPagesAccepted: false, tabRetained: true };
  fs.writeFileSync(output, JSON.stringify(report, null, 2), { flag: 'wx' });
  console.log(JSON.stringify(report));
} catch (error) {
  fs.writeFileSync(output, JSON.stringify({ outcome: 'BROWSER_ACCEPTANCE_FAILED', errorType: error.name,
    message: error.message, mutationClicks: 0, runtimeAuthorized: false, eightPagesAccepted: false }, null, 2), { flag: 'wx' });
  throw error;
} finally { await browser.close(); }

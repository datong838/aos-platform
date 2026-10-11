import playwright from '/Users/ddt/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.js';
import fs from 'node:fs';
import path from 'node:path';
const task = path.dirname(new URL(import.meta.url).pathname);
const output = path.join(task, 'management-eight-route-status-r4.json');
if (fs.existsSync(output)) throw new Error('Existing result: reconcile only');
const browser = await playwright.chromium.connectOverCDP('http://127.0.0.1:9244');
const page = await browser.contexts()[0].newPage();
const failures = [];
page.on('pageerror', error => failures.push(error.name));
const rows = [];
try {
  for (const route of ['cockpit', 'content-campaign', 'operations', 'creator-growth', 'media-studio', 'analyst', 'price-governance', 'customer']) {
    const response = await page.goto('http://127.0.0.1:18434/workshop/' + route);
    await page.getByText('当前工作台入口不可用', { exact: true }).waitFor({ timeout: 30000 });
    rows.push({ route: '/workshop/' + route, documentStatus: response.status(), actualState: 'UNAVAILABLE_NO_CURRENT_READY_INSTALLATION' });
  }
  await page.screenshot({ path: path.join(task, 'management-customer-current-gate-r4.png'), fullPage: true });
  const result = { rows, pageErrorTypes: failures, requestInterception: false, mockedResponses: false,
    eightPagesAccepted: false, runtimeAuthorized: false, tabRetained: true };
  fs.writeFileSync(output, JSON.stringify(result, null, 2), { flag: 'wx' });
  console.log(JSON.stringify(result));
} finally { await browser.close(); }

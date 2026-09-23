// W6-B: BG-01 registration panel UI acceptance for DS installation (c6812824).
// Flow: /apollo/assets -> click 安装管理 tab -> find DS row -> click -> capture RegistrationPanel.
const { chromium } = require('playwright-core');

const BASE = 'http://127.0.0.1:8434';
const OUT = '/Users/ddt/work/projects/ai_agent/aos-platform/.evidence';

(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const page = await browser.newPage({ viewport: { width: 1560, height: 950 } });

  try {
    await page.goto(`${BASE}/apollo/assets`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(2000);

    // 1. 点击「安装管理」tab
    const clicked = await page.evaluate(() => {
      const btn = [...document.querySelectorAll('button')].find((b) =>
        (b.textContent || '').trim() === '安装管理'
      );
      if (btn) { btn.click(); return true; }
      return false;
    });
    console.log('[1] clicked 安装管理 tab:', clicked);
    await page.waitForTimeout(2500);
    await page.screenshot({ path: `${OUT}/w6-b1-installations-tab.png`, fullPage: false });

    // 2. 找 DS 行 c6812824
    const found = await page.evaluate(() => document.body.innerText.includes('c6812824'));
    console.log('[2] DS id visible on page:', found);

    if (found) {
      // 3. 点击 DS 行
      const rowClicked = await page.evaluate(() => {
        const el = [...document.querySelectorAll('tr,li,article,section,div[class*=row]')].find((n) =>
          (n.textContent || '').includes('c6812824')
        );
        if (el) {
          const btn = el.querySelector('button,a,[role=button]') || el;
          btn.click();
          return el.tagName;
        }
        return null;
      });
      console.log('[3] clicked DS row container:', rowClicked);
      await page.waitForTimeout(3000);
      await page.screenshot({ path: `${OUT}/w6-b2-ds-installation-detail.png`, fullPage: false });

      // 4. 读 RegistrationPanel
      const panel = await page.evaluate(() => {
        const sec = document.querySelector('section[aria-label="电商业务登记"]');
        if (!sec) return null;
        return {
          heading: sec.querySelector('h3')?.textContent,
          allText: sec.textContent?.slice(0, 400),
          buttons: [...sec.querySelectorAll('button')].map((b) => b.textContent?.trim()),
        };
      });
      console.log('[4] RegistrationPanel:', JSON.stringify(panel, null, 1));

      // 5. allowedActions 与后端一致性复核（直调 API）
      const apiPanel = await page.evaluate(async () => {
        const res = await fetch('/api/v1/asset-control/installations/c6812824-a0c3-4adc-9ebc-d56178ae135c/registration', {
          headers: { Authorization: 'Bearer dev', 'X-Org-Id': 'org-org', 'X-Project-Id': 'dev-project' },
        });
        return { status: res.status, body: await res.text() };
      });
      console.log('[5] backend registration API:', apiPanel.status, apiPanel.body.slice(0, 300));
    }

    // 页面整图
    await page.screenshot({ path: `${OUT}/w6-b3-final-state.png`, fullPage: false });
    console.log('[done] screenshots saved to', OUT);
  } catch (e) {
    console.error('FAIL:', e.message);
    await page.screenshot({ path: `${OUT}/w6-b-fail.png` }).catch(() => {});
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();

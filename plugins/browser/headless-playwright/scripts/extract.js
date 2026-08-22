#!/usr/bin/env node
/**
 * headless-playwright: extract.js — 通用无头抓取/批量巡检
 * 用法:
 *   提取为 Markdown/文本: node extract.js <url-or-file-path> [输出.md]
 *   批量巡检:            node extract.js --check <urls.txt> [report.json]
 * urls.txt 每行一个 URL，# 注释；巡检默认检查 HTTP 状态(经浏览器)、标题非空、正文 > 50 字符
 * 输出 JSON 行供上层消费；失败退出码非 0
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

function toFileUrl(target) {
  if (/^https?:\/\//.test(target) || /^file:\/\//.test(target)) return target;
  const abs = path.resolve(target);
  if (!fs.existsSync(abs)) throw new Error(`File not found: ${abs}`);
  return 'file://' + abs;
}

async function loadOne(page, url) {
  const resp = await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(800); // 轻量等待，客户端渲染页面出内容
  const title = await page.title();
  const bodyText = (await page.evaluate(() => document.body ? document.body.innerText : '')).trim();
  return { httpStatus: resp ? resp.status() : null, title, bodyText };
}

(async () => {
  const args = process.argv.slice(2);
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });

  try {
    if (args[0] === '--check') {
      // ---- 批量巡检模式 ----
      const [_, listPath, reportArg] = args;
      if (!listPath) { console.error('用法: node extract.js --check <urls.txt> [report.json]'); process.exit(2); }
      const lines = fs.readFileSync(path.resolve(listPath), 'utf8').split('\n').map(l => l.trim()).filter(l => l && !l.startsWith('#'));
      if (lines.length === 0) { console.error('清单为空'); process.exit(2); }
      const report = []; let failed = 0;
      const page = await browser.newPage();
      for (const u of lines) {
        const entry = { url: u };
        const t0 = Date.now();
        try {
          const r = await loadOne(page, u);
          entry.httpStatus = r.httpStatus;
          entry.title = r.title;
          entry.bodyChars = r.bodyText.length;
          const problems = [];
          if (r.httpStatus && r.httpStatus >= 400) problems.push(`HTTP ${r.httpStatus}`);
          if (!r.title) problems.push('empty title');
          if (r.bodyText.length < 50) problems.push('body too short');
          entry.status = problems.length ? 'fail' : 'ok';
          entry.problems = problems;
        } catch (e) {
          entry.status = 'fail'; entry.error = e.message.split('\n')[0]; entry.problems = [entry.error];
        }
        entry.ms = Date.now() - t0;
        if (entry.status === 'fail') failed++;
        report.push(entry);
        console.log(`[${entry.status}] ${u}${entry.problems && entry.problems.length ? ' — ' + entry.problems.join('; ') : ''}`);
      }
      await page.close();
      const reportPath = reportArg ? path.resolve(reportArg) : path.join('/tmp', 'pw_check_' + Date.now() + '.json');
      fs.writeFileSync(reportPath, JSON.stringify({ total: lines.length, failed, generatedAt: new Date().toISOString(), pages: report }, null, 2));
      console.log(`\n巡检完成: ${lines.length - failed}/${lines.length} 正常, report: ${reportPath}`);
      process.exit(failed > 0 ? 1 : 0);

    } else {
      // ---- 单页提取模式 ----
      const [target, outArg] = args;
      if (!target) { console.error('用法: node extract.js <url-or-file-path> [输出.md]'); process.exit(2); }
      const url = toFileUrl(target);
      const page = await browser.newPage();
      const r = await loadOne(page, url);
      const md = `# ${r.title || '(无标题)'}\n\n> 来源: ${url}\n> HTTP ${r.httpStatus ?? 'file'}\n\n---\n\n${r.bodyText}\n`;
      const out = outArg ? path.resolve(outArg) : '/tmp/pw_extract_' + Date.now() + '.md';
      fs.writeFileSync(out, md);
      console.log(JSON.stringify({ ok: true, url, out, httpStatus: r.httpStatus, title: r.title, bodyChars: r.bodyText.length }));
      await page.close();
    }
  } finally {
    await browser.close();
  }
})().catch(e => { console.error('FAIL:', e.message); process.exit(1); });

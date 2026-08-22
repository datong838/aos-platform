#!/usr/bin/env node
/**
 * headless-playwright: shot.js — 单页无头截图
 * 用法: node shot.js <url-or-file-path> [输出.png] [宽x高]
 * 退出码: 0=成功 1=页面加载/校验失败 2=参数错误
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

(async () => {
  const [target, outArg, sizeArg] = process.argv.slice(2);
  if (!target) { console.error('用法: node shot.js <url-or-file-path> [输出.png] [宽x高]'); process.exit(2); }
  const out = outArg || '/tmp/pw_shot_' + Date.now() + '.png';
  const [w, h] = (sizeArg || '1560x900').split('x').map(Number);

  const url = toFileUrl(target);
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  try {
    const page = await browser.newPage({ viewport: { width: w, height: h } });
    await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(1500); // Tailwind CDN 运行时注入
    await page.screenshot({ path: out, fullPage: false });
    const size = fs.statSync(out).size;
    // 白图守卫：小于 5KB 视为渲染失败
    if (size < 5 * 1024) { console.error(`FAIL: screenshot too small (${size}B), likely blank: ${out}`); process.exit(1); }
    console.log(JSON.stringify({ ok: true, url, out, bytes: size }));
  } finally {
    await browser.close();
  }
})().catch(e => { console.error('FAIL:', e.message); process.exit(1); });

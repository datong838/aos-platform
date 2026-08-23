#!/usr/bin/env node
/**
 * headless-playwright: pdf.js — 单页无头生成 PDF
 * 用法: node pdf.js <url-or-file-path> [输出.pdf] [宽x高]
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
  if (!target) { console.error('用法: node pdf.js <url-or-file-path> [输出.pdf] [宽x高]'); process.exit(2); }
  const out = outArg || '/tmp/pw_pdf_' + Date.now() + '.pdf';
  const [w, h] = (sizeArg || '1560x900').split('x').map(Number);

  const url = toFileUrl(target);
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  try {
    const page = await browser.newPage({ viewport: { width: w, height: h } });
    await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(1500);
    await page.pdf({ path: out, width: `${w}px`, height: `${h}px`, printBackground: true });
    const size = fs.statSync(out).size;
    if (size < 5 * 1024) { console.error(`FAIL: pdf too small (${size}B): ${out}`); process.exit(1); }
    console.log(JSON.stringify({ ok: true, url, out, bytes: size }));
  } finally {
    await browser.close();
  }
})().catch(e => { console.error('FAIL:', e.message); process.exit(1); });

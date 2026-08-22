#!/usr/bin/env node
/**
 * headless-playwright: batch_shot.js — 批量无头截图（通用）
 * 两种输入（自动识别）：
 *   1. 本地目录：node batch_shot.js <html目录> <输出目录> [宽x高]
 *   2. URL 清单：node batch_shot.js <urls.txt> <输出目录> [宽x高]
 *      urls.txt 每行一个 http(s):// 或 file:// 地址，# 开头为注释
 * 输出: 每页同名 PNG + report.json；任一页失败退出码非 0
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

function nameForUrl(u, idx) {
  // 从 URL 提取安全文件名：去协议、域名中的冒号斜杠替换、保留路径特征
  let s = u.replace(/^https?:\/\//, '').replace(/^file:\/\//, '');
  s = s.replace(/[/?#:*|"<>\\]/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '');
  if (s.length > 80) s = s.slice(0, 80); // 防超长文件名
  return (s || `page_${idx + 1}`) + '.png';
}

(async () => {
  const [inputArg, outDirArg, sizeArg] = process.argv.slice(2);
  if (!inputArg || !outDirArg) {
    console.error('用法: node batch_shot.js <html目录|urls.txt> <输出目录> [宽x高]');
    process.exit(2);
  }
  const input = path.resolve(inputArg);
  const outDir = path.resolve(outDirArg);
  if (!fs.existsSync(input)) { console.error(`输入不存在: ${input}`); process.exit(2); }
  fs.mkdirSync(outDir, { recursive: true });
  const [w, h] = (sizeArg || '1560x900').split('x').map(Number);

  // 构建任务列表：目录 → file:// 列表；文本清单 → 逐行 URL
  const tasks = [];
  if (fs.statSync(input).isDirectory()) {
    const files = fs.readdirSync(input).filter(f => f.endsWith('.html')).sort();
    if (files.length === 0) { console.error(`目录内无 .html 文件: ${input}`); process.exit(2); }
    for (const f of files) {
      tasks.push({ url: 'file://' + path.join(input, f), out: path.join(outDir, f.replace(/\.html$/, '.png')) });
    }
  } else {
    const lines = fs.readFileSync(input, 'utf8').split('\n').map(l => l.trim()).filter(l => l && !l.startsWith('#'));
    if (lines.length === 0) { console.error(`清单为空: ${input}`); process.exit(2); }
    lines.forEach((u, i) => tasks.push({ url: u, out: path.join(outDir, nameForUrl(u, i)) }));
  }

  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const report = [];
  let failed = 0;

  for (const t of tasks) {
    const t0 = Date.now();
    const entry = { url: t.url, out: t.out };
    try {
      const page = await browser.newPage({ viewport: { width: w, height: h } });
      await page.goto(t.url, { waitUntil: 'networkidle', timeout: 30000 });
      await page.waitForTimeout(1500); // 等动态样式/字体注入（如 Tailwind CDN）
      await page.screenshot({ path: t.out, fullPage: false });
      const bytes = fs.statSync(t.out).size;
      if (bytes < 5 * 1024) throw new Error(`screenshot too small (${bytes}B), likely blank`);
      entry.status = 'ok';
      entry.bytes = bytes;
      await page.close();
    } catch (e) {
      entry.status = 'fail';
      entry.error = e.message.split('\n')[0];
      failed++;
    }
    entry.ms = Date.now() - t0;
    report.push(entry);
    console.log(`[${entry.status}] ${path.basename(t.out)} (${entry.ms}ms)`);
  }
  await browser.close();

  const reportPath = path.join(outDir, 'report.json');
  fs.writeFileSync(reportPath, JSON.stringify({ total: tasks.length, failed, generatedAt: new Date().toISOString(), pages: report }, null, 2));
  console.log(`\n完成: ${tasks.length - failed}/${tasks.length} 成功, report: ${reportPath}`);
  process.exit(failed > 0 ? 1 : 0);
})().catch(e => { console.error('FAIL:', e.message); process.exit(1); });

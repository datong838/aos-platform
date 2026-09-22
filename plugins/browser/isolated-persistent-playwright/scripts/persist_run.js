#!/usr/bin/env node
/**
 * persist_run.js — Profile 隔离持久 Playwright 通用执行器
 *
 * 执行流程（与 SKILL.md 一致）：
 *   1. 环境检查：确认 userDataDir 存在，不存在则创建；加进程锁防止多实例抢目录
 *   2. 启动浏览器：launchPersistentContext（默认有头 + 系统 Chrome）
 *   3. 访问目标 URL
 *   4. 登录态检测：命中特征则继续；未命中则保持窗口打开，等待人工登录，登录后自动落盘
 *   5. 执行业务操作：--task 指向 CommonJS 模块，导出 async (page, ctx) => {}
 *   6. 结果确认：截图留证 + result JSON 日志
 *   7. 关闭 context，数据自动写入 userDataDir
 *
 * 用法：
 *   node persist_run.js --profile <userDataDir> --url <https://...> \
 *     [--login-check <selector>] [--login-wait <sec>] \
 *     [--task <task.js>] [--shot <out.png>] [--log <out.json>] \
 *     [--proxy <http://host:port>] [--headless] [--timeout <ms>] [--ua <string>]
 *
 * 退出码：0 成功；2 参数错误；3 Profile 被占用；4 登录等待超时；5 业务/导航失败
 */

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

// ---------- 参数解析 ----------
function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i++) {
    const k = argv[i];
    if (!k.startsWith('--')) continue;
    const next = argv[i + 1];
    if (k === '--headless') { args.headless = true; continue; }
    if (next === undefined || next.startsWith('--')) { args[k.slice(2)] = true; continue; }
    args[k.slice(2)] = next;
    i++;
  }
  return args;
}

const args = parseArgs(process.argv);
const PROFILE = args.profile;
const URL = args.url;

function fatal(code, msg) { console.error(`[persist_run] FATAL(${code}): ${msg}`); process.exit(code); }

if (!PROFILE) fatal(2, '缺少 --profile <userDataDir>');
if (!URL) fatal(2, '缺少 --url <https://...>');

const profileDir = path.resolve(PROFILE);
const lockFile = profileDir + '.lock';
const loginTimeoutSec = parseInt(args['login-wait'] || '300', 10);
const navTimeout = parseInt(args.timeout || '45000', 10);

// 固定指纹：所有账号统一，避免同账号跨次漂移
const FINGERPRINT = {
  viewport: { width: 1560, height: 900 },
  locale: 'zh-CN',
  timezoneId: 'Asia/Shanghai',
};

(async () => {
  // ---- Step 1: 环境检查 + 进程锁 ----
  fs.mkdirSync(profileDir, { recursive: true });
  if (fs.existsSync(lockFile)) {
    const prev = parseInt(fs.readFileSync(lockFile, 'utf8').trim(), 10);
    let alive = false;
    try { process.kill(prev, 0); alive = true; } catch (_) {}
    if (alive) fatal(3, `Profile 被占用（PID ${prev} 仍存活）：${lockFile}。禁止两个实例共用同一 userDataDir。`);
    fs.unlinkSync(lockFile); // 残留死锁，清理
  }
  fs.writeFileSync(lockFile, String(process.pid));
  const releaseLock = () => { try { fs.unlinkSync(lockFile); } catch (_) {} };
  process.on('exit', releaseLock);
  process.on('SIGINT', () => process.exit(130));

  const result = {
    started_at: new Date().toISOString(),
    profile: profileDir,
    url: URL,
    headless: !!args.headless,
    steps: {},
    ok: false,
  };

  let context;
  try {
    // ---- Step 2: 启动（launchPersistentContext）----
    const launchOpts = {
      headless: !!args.headless,
      channel: 'chrome', // 系统 Chrome；如需独立 Chromium 用 executablePath 指定
      viewport: FINGERPRINT.viewport,
      locale: FINGERPRINT.locale,
      timezoneId: FINGERPRINT.timezoneId,
      args: ['--disable-blink-features=AutomationControlled'],
    };
    if (args.proxy) launchOpts.proxy = { server: args.proxy };
    if (args.ua) launchOpts.userAgent = args.ua;
    context = await chromium.launchPersistentContext(profileDir, launchOpts);
    result.steps.launch = 'ok';

    const page = context.pages()[0] || await context.newPage();

    // ---- Step 3: 访问目标 URL ----
    await page.goto(URL, { waitUntil: 'domcontentloaded', timeout: navTimeout });
    result.steps.goto = 'ok';

    // ---- Step 4: 登录态检测 ----
    const loginSel = args['login-check'];
    if (loginSel) {
      let loggedIn = await page.locator(loginSel).first().isVisible().catch(() => false);
      if (!loggedIn) {
        console.log(`[persist_run] 未检测到登录特征（${loginSel}），请在打开的窗口中人工登录（扫码/短信/验证码）。等待最多 ${loginTimeoutSec}s ...`);
        const deadline = Date.now() + loginTimeoutSec * 1000;
        while (Date.now() < deadline) {
          await page.waitForTimeout(2000);
          // 登录动作可能触发跳转，始终在当前最新页面上探测
          const cur = context.pages().slice(-1)[0] || page;
          loggedIn = await cur.locator(loginSel).first().isVisible().catch(() => false);
          if (loggedIn) break;
        }
        if (!loggedIn) fatal(4, `登录等待超时（${loginTimeoutSec}s），登录态未建立。`);
      }
      result.steps.login = 'ok';
      console.log('[persist_run] 登录态已确认，Profile 中 Cookie 将随关闭自动落盘。');
    } else {
      result.steps.login = 'skipped (no --login-check)';
    }

    // ---- Step 5: 业务操作（外部任务模块，可选）----
    if (args.task) {
      const taskPath = path.resolve(args.task);
      if (!fs.existsSync(taskPath)) fatal(5, `任务脚本不存在: ${taskPath}`);
      const runTask = require(taskPath);
      await runTask(page, context, { result });
      result.steps.task = path.basename(taskPath);
      console.log('[persist_run] 业务任务执行完毕。');
    } else {
      result.steps.task = 'skipped (no --task)';
    }

    // ---- Step 6: 结果确认（截图 + 日志）----
    if (args.shot) {
      const shotPath = path.resolve(args.shot);
      fs.mkdirSync(path.dirname(shotPath), { recursive: true });
      const cur = context.pages().slice(-1)[0] || page;
      await cur.screenshot({ path: shotPath, fullPage: false });
      result.screenshot = shotPath;
      result.steps.screenshot = 'ok';
    }

    result.ok = true;
  } catch (err) {
    result.error = String(err && err.message || err);
    result.ok = false;
  } finally {
    // ---- Step 7: 关闭 context，数据自动落盘 ----
    const logPath = args.log ? path.resolve(args.log) : path.join(profileDir, 'last-run-result.json');
    try { fs.writeFileSync(logPath, JSON.stringify(result, null, 2)); } catch (_) {}
    if (context) { try { await context.close(); } catch (_) {} }
    console.log(`[persist_run] 完成 ok=${result.ok}，日志: ${logPath}`);
    process.exit(result.ok ? 0 : 5);
  }
})();

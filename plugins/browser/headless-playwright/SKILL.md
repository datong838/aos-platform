---
name: headless-playwright
description: Run headless-browser batch jobs with Playwright (playwright-core + system Chrome) for visual-mock screenshots, PDF generation, CI smoke checks, and bulk extraction. Use when tasks are repeatable, unattended, and do not need the user's real login state or a visible window. Do NOT use for strong-risk sites (anti-bot challenges), real login reuse, or any interactive takeover — those belong to kitewright (headed) or the control-* skills.
---

# Headless Playwright — 无头浏览器批处理

## 是什么

一个**通用的无头浏览器批处理能力插件**：任何网页（`http(s)://`）或本地 HTML（`file://`）的批量截图、PDF 生成、内容提取、站点巡检。基于 `playwright-core` + 系统已安装的 Google Chrome（`channel: 'chrome'`），不下载独立 Chromium 二进制，不依赖任何 Chrome 扩展。它是数字同事（Agent）调用的工具，自身不是数字同事实体。

视觉稿（`docs/palantier/foundry/html/`）只是典型用例之一，见"视觉稿依赖"节的专项守卫。

**引擎**：Node.js `playwright-core`（受控 workspace `/Users/ddt/.workbuddy/binaries/node/workspace/node_modules`，经 `NODE_PATH` 引用）。

## 与并列三技能的边界（选择器）

| 技能 | 有头/无头 | 登录态 | 典型任务 |
|---|---|---|---|
| **headless-playwright**（本技能） | 无头 | 临时（或显式注入 storage_state） | 任意网页/本地 HTML 的批量截图、PDF、提取、巡检 |
| kitewright | 有头（默认） | 独立临时 profile，可 save/restore | 真机交互验收、风控敏感站点、E2E |
| control-dedicated-chrome | 有头 | 专用持久 profile（手动首登） | 运营发布等需要持久登录的操作 |
| control-existing-chrome | 有头 | 用户日常 Chrome 真实登录态 | 必须复用用户已打开会话的任务 |

**选择规则**：
1. 任务要无人值守、可批量、不需要真实登录 → 本技能
2. 站点有强风控（验证码、Cloudflare 挑战、`navigator.webdriver` 检测）→ 降级用 kitewright 有头模式
3. 必须复用用户登录态 → control-existing-chrome / control-dedicated-chrome
4. 本技能不与用户日常 Chrome 发生任何交互，不触碰其 profile/cookie

## 运行前提

- Node.js：`node`（v22 可用，系统 PATH 与受控路径 `/Users/ddt/.workbuddy/binaries/node/versions/22.22.2/bin/node` 均可）
- playwright-core：**已内置在本技能目录 `node_modules/`（13M，随目录走，无需 NODE_PATH）**；若被清理，重装：`cd <本技能目录> && npm install`
- 系统 Chrome：`/Applications/Google Chrome.app`（`channel: 'chrome'` 自动定位；无需 CDP 端口、无需 remote debugging）
- 联网：页面依赖 CDN 资源时必须可达（见"视觉稿依赖"节）

## 标准调用模板

```bash
node <scripts/xxx.js> [参数]   # 直接跑，无需任何环境变量
```

（兼容写法：受控绝对路径 `/Users/ddt/.workbuddy/binaries/node/versions/22.22.2/bin/node` 效果等同）

四个内置脚本（`scripts/` 下，全部通用，支持任意 `http(s)://` / `file://` / 本地路径，不限于视觉稿）：

1. **`shot.js`** — 单页截图：`node shot.js <url-or-file-path> [输出.png] [宽x高]`
2. **`batch_shot.js`** — 批量截图（双模式，自动识别输入）：本地 HTML 目录 **或** URL 清单（`urls.txt` 每行一个地址，`#` 注释）：`node batch_shot.js <html目录|urls.txt> <输出目录> [宽x高]`
3. **`pdf.js`** — 单页 PDF：`node pdf.js <url-or-file-path> [输出.pdf] [宽x高]`
4. **`extract.js`** — 抓取/巡检双模式：
   - 提取：`node extract.js <url> [输出.md]`（标题+正文转 Markdown）
   - 巡检：`node extract.js --check <urls.txt> [report.json]`（HTTP 状态 + 标题非空 + 正文长度三项检查）

自写脚本的核心骨架：

```js
const { chromium } = require('playwright-core');
const browser = await chromium.launch({ headless: true, channel: 'chrome' });
const page = await browser.newPage({ viewport: { width: 1560, height: 900 } });
await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
await page.waitForTimeout(1500); // 等 Tailwind CDN 运行时注入
await page.screenshot({ path: out, fullPage: false });
await browser.close();
```

## 视觉稿依赖（docs/palantier/foundry/html 目录）

- 布局样式依赖 `https://cdn.tailwindcss.com` **运行时生成**：断网/代理故障时页面渲染为无样式堆叠，截图仍会成功但内容是错的
- 本地 `assets/demo.css`、`assets/demo.js` 为相对路径，`file://` 协议下正常加载
- **正确性守卫**：截图后校验页面关键元素（如 `.p-nav-global` 可见、卡片数 > 0），失败则标记 report 而不是静默输出白图
- 2026-08-20 已实测：`agent-registry.html` 无头渲染正常（11 张卡片、导航可见、267KB 截图）

## 无头模式已知坑

| 症状 | 原因 | 处理 |
|---|---|---|
| 截图全白/空白 | 等待不足或 CDN 未加载完 | `networkidle` + 固定 1500ms；增加关键元素校验 |
| 样式丢失（元素堆叠） | `cdn.tailwindcss.com` 不可达 | 先 `curl` 探活；失败改本地内联或推迟任务 |
| 站点停留 "Please wait..." | 无头被反爬识别（`navigator.webdriver=true`） | 降级 kitewright 有头；本技能不硬闯 |
| 字体缺失/方块字 | 无头环境字体不全 | 本机 macOS 系统字体一般够用；容器环境需装字体 |
| 登录后页面拿不到 | storage_state 过期 | 重新生成 storage_state；强风控站点改用 dedicated-chrome |

## 登录态注入（可选，弱风控站点）

需要带登录态批量访问时，先在 kitewright 有头模式完成登录并导出 `storage_state.json`，本技能用：

```js
const ctx = await browser.newContext({ storageState: 'path/to/storage_state.json' });
```

约束：`storage_state.json` 含凭据，**禁止提交 git**（加入 .gitignore）；强风控站点（微信小店、淘宝等）不用此法，走 browser-pilot / dedicated-chrome。

## 输出与证据

- 截图/PDF 输出到任务指定目录，默认放 `/tmp` 或项目 `output/`，不写入本插件目录
- 批量任务生成 `report.json`（每页：url、状态 ok/fail、元素校验结果、耗时）
- 失败不静默：任一页失败时 report 标记，退出码非 0

## 环境与安全边界

- 本机 macOS + 系统 Chrome；Windows/Linux 未经校验不承诺
- 不修改系统 Chrome 任何配置；每次运行创建临时 context，用完即关
- 不读取、不导出、不存储用户浏览器 profile/cookie/密码
- 下载类站点、支付类操作不在本技能范围内

---
name: isolated-persistent-playwright
description: 驱动独立 Chromium/系统 Chrome，以 launchPersistentContext 持久化 Profile 隔离多账号，完成需要登录态、人工介入的网页自动化任务。适合运营发布、多账号管理、数据填报等有头交互场景；不适合无头批量截图/提取（请用 headless-playwright）。
---

# Profile 隔离持久 Playwright

## 是什么

一个通用浏览器自动化能力，基于 `playwright-core` + 系统 Chrome，通过 `launchPersistentContext` 使用独立 `userDataDir` 持久化 Cookie、LocalStorage 等登录态，实现多账号互不干扰、跨会话复用的自动化任务。默认有头运行，便于处理验证码、扫码、短信确认等需要人工介入的环节；关闭浏览器后登录态自动保存在 Profile 目录，下次直接复用。

Playwright 自带的独立 Chromium / 系统 Chrome 与日常使用的 Chrome 完全隔离——相当于一个干净的、专供自动化使用的浏览器；每个账号一套独立 Cookie Profile，互不干扰，可同时管理多个账号，或反复测试同一流程而无需反复登录。

## 与 headless-playwright 的分工

| 维度 | headless-playwright | 本技能（Profile 隔离持久 Playwright） |
|---|---|---|
| 运行模式 | 无头 | 有头为主，可切无头 |
| Profile | 临时，用完即弃 | 持久独立目录，跨会话复用 |
| 登录态 | 不主动保存 | 永久保存在 userDataDir |
| 典型任务 | 截图、PDF、提取、站点巡检 | 登录后操作、日常发布、账号管理 |
| 风控策略 | 不硬闯，失败即放弃 | 有头 + 持久环境更接近真实用户 |
| 多账号 | 不支持 | 每个账号一个目录，完全隔离 |

选择规则：
1. 无需登录、无人值守、只要结果 → 用 headless-playwright
2. 需要登录、需要长期保存会话、可能有人工介入 → 用本技能
3. 需要复用用户当前已打开的浏览器 → 走 control-existing-chrome 类方案

## 运行前提

- Node.js v20+（受控路径 `/Users/ddt/.workbuddy/binaries/node/versions/22.22.2-2/bin/node`）
- `playwright-core` **已内置在本技能目录 `node_modules/`（随目录走，无需 NODE_PATH）**；若被清理，重装：`cd <本技能目录> && npm install`
- 系统 Chrome（`channel: 'chrome'` 自动定位）或独立 Chromium（`executablePath` 指定）
- 为每个账号准备独立 `userDataDir` 目录（如 `~/aos-profiles/creator-a`）

## 核心配置参数

| 参数 | 说明 |
|---|---|
| `headless: false` | 默认有头；需无人值守时可改 true，但强风控站点不建议 |
| `channel: 'chrome'` | 使用系统 Chrome；也可用 `executablePath` 指定独立 Chromium |
| `userDataDir` | 独立目录，存储 Cookie、缓存、LocalStorage，是隔离的关键 |
| `proxy` | 多账号时建议每个账号配置不同代理 IP |
| `viewport` / `locale` / `timezoneId` | 固定统一，避免指纹漂移 |
| `args` | 建议追加 `--disable-blink-features=AutomationControlled` |

## 标准调用模板

内置执行器 `scripts/persist_run.js`（一条命令走完整个执行流程）：

```bash
node <本技能目录>/scripts/persist_run.js \
  --profile ~/aos-profiles/creator-a \
  --url https://example.com/dashboard \
  --login-check "text=工作台" \
  --shot /tmp/creator-a.png \
  --task ./my-task.js            # 可选：导出 async (page, context) => {}
  # 可选: --proxy http://host:port | --headless | --login-wait 300 | --timeout 45000 | --ua "..."
```

执行器内置能力：
1. **Profile 加锁**：`<userDataDir>.lock` + PID 存活检测，防止两个实例抢同一目录
2. **登录等待**：`--login-check` 选择器未命中时保持窗口打开，轮询等待人工登录（默认最多 300s），登录后自动落盘
3. **指纹固定**：viewport 1560x900 / locale zh-CN / timezone Asia/Shanghai 统一写死
4. **结果留证**：`--shot` 截图 + 每次运行写 `last-run-result.json` 到 Profile 目录
5. **退出码**：0 成功 / 2 参数错误 / 3 Profile 被占用 / 4 登录超时 / 5 业务失败

自写脚本核心骨架（与执行器等价的最小写法）：

```js
const { chromium } = require('playwright-core');
const context = await chromium.launchPersistentContext(userDataDir, {
  headless: false,
  channel: 'chrome',
  viewport: { width: 1560, height: 900 },
  locale: 'zh-CN',
  timezoneId: 'Asia/Shanghai',
  args: ['--disable-blink-features=AutomationControlled'],
});
const page = context.pages()[0] || await context.newPage();
await page.goto(url, { waitUntil: 'domcontentloaded' });
// ... 业务操作 ...
await context.close(); // 关闭即落盘，无需显式 save
```

## 执行流程

1. **环境检查**：确认 `userDataDir` 存在，不存在则创建；加锁防多实例。
2. **启动浏览器**：调用 `launchPersistentContext`。
3. **访问目标 URL**。
4. **登录态检测**：通过页面特征判断是否已登录；未登录则暂停等待人工登录，登录后自动保存。
5. **执行业务操作**：上传、填写、点击、提交等。
6. **结果确认**：截图留证、输出日志。
7. **关闭 context**，数据自动落盘。

## 多账号隔离最佳实践

- 每个账号分配唯一 `userDataDir`，禁止两个实例共用同一目录（执行器有锁兜底，但根上靠目录唯一）。
- 每个实例独立进程，程序结束前关闭 context。
- 多账号同时运行时，务必为每个账号配置不同出口 IP（代理，`--proxy`），否则平台可通过 IP 关联账号。
- 保持指纹一致：固定 User-Agent、locale、timezone、viewport（执行器已内置统一指纹）。
- 定期备份 `userDataDir`，避免数据丢失需要重新登录。

## 风控注意事项

- 强风控站点可能检测 `navigator.webdriver`、CDP 痕迹、行为异常，可结合 `--disable-blink-features=AutomationControlled`、随机延时、模拟鼠标轨迹等手段。
- 若出现验证码，**不要自动破解**，由人工在有头窗口中完成。
- 默认有头就是为了给扫码、短信验证等环节留人工入口。
- 如果无头模式被检测，切回有头。

## 已知坑

| 症状 | 可能原因 | 处理 |
|---|---|---|
| 多个实例抢同一个 userDataDir | 误用同一目录 | 确保唯一目录，执行器已加 lock 文件兜底 |
| Cookie 保存后下次失效 | 站点加密指纹绑定 | 保持指纹固定，代理 IP 稳定 |
| 有头窗口被识别 | AutomationControlled 未禁用 | 加 args 参数，检查其他指纹 |
| 登录需要扫码但窗口不可见 | headless 模式 | 改用有头或添加虚拟显示 |
| 浏览器启动慢 | Profile 过大 | 定期清理缓存 |

## 安全边界

- 本技能不读取、不修改用户日常 Chrome 的任何数据。
- userDataDir 中包含敏感登录态，**禁止提交 git**（.gitignore 掉 profiles/ 与 *.lock），注意文件权限（建议 0700）。
- 仅用于合法合规的自动化任务，遵守目标网站服务条款。

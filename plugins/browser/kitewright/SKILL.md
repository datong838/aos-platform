---
name: "kitewright"
description: "Launch and control an isolated Chrome/Chromium through Kitewright MCP and CDP for local browser acceptance, batch E2E, screenshots, accessibility snapshots, console/network capture, PDF, and disposable-session automation. Use when an independent temporary browser profile is appropriate. Do not use when a task must reuse the user's existing ordinary Chrome tabs or login state, or when a strong-risk site challenges the automation browser."
---

# Kitewright — 独立浏览器自动化

## 是什么

一个**通用的浏览器操控能力插件**（浏览器自动化引擎），底层通过 Chrome DevTools Protocol (CDP) 直接控制原生 Chrome/Chromium，**不依赖任何 Chrome 扩展、Electron 内嵌浏览器或第三方 browser MCP**。它是数字同事（Agent）调用的工具，自身不是数字同事实体。

**引擎**：Kitewright MCP Server — Rust 编写的 CDP 自动化引擎，24 个高级工具（含状态保存/恢复、对话框处理），自动生命周期管理，per-session 上下文隔离，actionability auto-waiting（可见 + 可用 + 未被遮挡 + 稳定才操作）。

**kite 二进制已内置**在插件 `bin/` 目录下（arm64 Mach-O），无需安装 Rust 或 Node.js。

## 运行边界：独立启动，不复用普通 Chrome

Kitewright **自行启动一个独立 Chrome/Chromium**，并为每次启动创建临时 `user_data_dir`。它不连接用户当前打开的普通 Chrome，不复用现有标签页、Profile 或登录态。

当前源码加入的主要启动参数包括：

```text
no-sandbox
in-process-gpu
disable-gpu
disable-extensions
mute-audio
disable-dev-shm-usage
no-first-run
no-default-browser-check
disable-background-networking
disable-component-update
disable-sync
disable-default-apps
hide-scrollbars
disk-cache-dir=...
window-size=...
```

源码没有显式加入名为 `webdriver=true` 的命令行参数。但在 2026-08-12 的掘金现场中，页面只读检查实际观察到 `navigator.webdriver=true`，随后停留在 `Please wait...` 前置挑战，没有进入登录流程。这是当前构建与该站点的一次真实观察，不是掘金官方规则，也不代表所有站点都会如此。

遇到前置挑战、CAPTCHA 或风险验证时：停止操作，不修改指纹、不隐藏 webdriver、不绕过挑战。若任务必须复用用户已经登录的普通 Chrome，改用独立的 `control-existing-chrome` Skill。

## 什么时候调用

**适合独立自动化浏览器的场景**：

1. **前端页面验收** — 代码改动后截图 + 文字检查 + 断言
2. **自动化表单操作** — 测试环境填表、提交、分页浏览
3. **数据采集** — 抓取页面内容、提取结构化数据（含 Shadow DOM 穿透）
4. **UI 探索** — 截图 + 无障碍树快照，理解页面结构
5. **端到端测试** — 导航 → 交互 → 验证 → 截图存证
6. **PDF 导出** — 页面或 HTML 转 PDF
7. **调试** — 控制台日志捕获、网络请求监控

**不调用的场景**：
- 纯 API 测试（用 curl / httpie 即可）
- 静态代码分析（不需要浏览器）
- 单元测试（用 Vitest / pytest）
- 必须复用用户普通 Chrome 已登录会话的操作（用 `control-existing-chrome`）
- 已出现前置挑战、CAPTCHA、风险验证或浏览器安全警告

## 架构

```
┌──────────────────────────────────────────────────────┐
│           Host System (AOS / 任意系统)                 │
│                                                      │
│  ┌────────────────────────────────────────────────┐ │
│  │  Agent Layer (SKILL.md — 你在这里)               │ │
│  │  定义 WHAT：验收什么页面、检查什么文字、填什么表  │ │
│  └──────────────────┬─────────────────────────────┘ │
│                     │ Python SDK / HTTP API           │
│  ┌──────────────────▼─────────────────────────────┐ │
│  │  Engine Adapter (engine_adapter.py)             │ │
│  │  Kitewright → KitewrightMCP.call_tool()       │ │
│  └──────────────────┬─────────────────────────────┘ │
│                     │ MCP JSON-RPC                    │
│  ┌──────────────────▼─────────────────────────────┐ │
│  │  kite MCP Server (bin/kite, HTTP :8090)        │ │
│  │  21 工具 / auto-wait / session 隔离 / 空闲回收 │ │
│  └──────────────────┬─────────────────────────────┘ │
│                     │ CDP 协议                        │
│  ┌──────────────────▼─────────────────────────────┐ │
│  │  Chrome / Chromium (原生，无扩展)                │ │
│  └────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

## 内置 kite 二进制

插件 `bin/kite` 是 Kitewright 的编译产物（arm64 Mach-O, ~12MB）。

**重新编译**（如需更新）：
```bash
cd /path/to/kitewright
cargo build --release -p kitewright
cp target/release/kite /path/to/kitewright/bin/kite
```

**其他平台**：kite 是平台相关的二进制，跨平台使用时需重新编译或用 `npx -y @kitewright/mcp` 替代。

## 通信协议：MCP Streamable HTTP（内部细节）

> 以下内容仅用于排查通信层问题。正常使用 `engine_adapter.py` 的 `Kitewright` 类时无需关心。

kite（默认 HTTP 模式）**不使用普通 JSON-RPC over HTTP**，而是使用 **MCP Streamable HTTP** 协议：

```
┌──────────┐     1. POST /mcp (initialize)        ┌──────────┐
│  Client  │ ─────────────────────────────────────▶│   kite   │
│          │ ◀─────────────────────────────────── │  :8090   │
│          │     2. 响应头: mcp-session-id: xxx     │          │
│          │                                       │          │
│          │     3. POST /mcp (tools/call)         │          │
│          │     Header: mcp-session-id: xxx        │          │
│          │     Header: Accept: application/json,  │          │
│          │             text/event-stream          │          │
│          │ ─────────────────────────────────────▶│          │
│          │ ◀─────────────────────────────────── │          │
│          │     4. SSE 响应: data: {json}\n\n      │          │
└──────────┘                                       └──────────┘
```

**关键规则**：
1. 首次请求必须是 `initialize`，从响应头提取 `mcp-session-id`
2. 后续所有请求**必须携带** `mcp-session-id` 头 + `Accept: application/json, text/event-stream` 头
3. 响应体是 **SSE 格式**（`data: {json}\n\n`），需要解析 `data:` 前缀提取实际 JSON
4. 跳过 initialize 直接调 `tools/call` → **HTTP 400**

`engine_adapter.py` 中 `KitewrightMCP._init_session()` + `call_tool()` 已完整封装此流程。

## 工具 API

### 导航与读取

| 工具 | 参数 | 说明 |
|------|------|------|
| `navigate` | `url, lite?` | 导航到 URL，返回标题+URL+可见文本 |
| `screenshot` | `full_page?` | 截图，返回 PNG |
| `extract` | `selector, attribute?` | 按选择器提取文本/属性 |
| `extract_markdown` | 无 | 主内容转 Markdown |
| `snapshot` | `diff?` | 无障碍树快照（穿透 Shadow DOM） |

### 交互

| 工具 | 参数 | 说明 |
|------|------|------|
| `click` | `selector, timeout_ms?` | 点击元素（自动滚动+等待） |
| `type` | `selector, text, clear?, press_enter?` | 输入文字 |
| `fill_form` | `fields: [{selector, value}]` | 批量填表 |
| `select_option` | `selector, value?/label?` | 选择下拉 |
| `hover` | `selector` | 鼠标悬停 |
| `press_key` | `key` | 键盘按键 |
| `handle_dialog` | `accept, prompt_text?` | 处理弹窗 |
| `wait_for` | `selector?/text?, timeout_ms?` | 等待元素/文本出现 |

### 验证

| 工具 | 参数 | 说明 |
|------|------|------|
| `assert` | `condition_selector?/text?, should_exist?` | 结构化断言 |
| `console` | `clear?` | 获取控制台消息 |
| `network` | `clear?, filter?` | 获取网络请求 |

### 状态

| 工具 | 参数 | 说明 |
|------|------|------|
| `save_state` | 无 | 保存 cookies + localStorage |
| `restore_state` | `state` | 恢复登录态 |

### 输出

| 工具 | 参数 | 说明 |
|------|------|------|
| `pdf` | `format?, landscape?, ...` | 页面转 PDF |

### 高级直通

| 方法 | 说明 |
|------|------|
| `call_raw(tool, params)` | 直接调用任意 Kitewright MCP 工具，绕过 Python 封装 |

## 选择器语法

Kitewright 原生支持三种选择器：

- **CSS**（默认）：`#login`, `button.primary`, `input[name="email"]`
- **文本**：`text=提交` — 第一个可见且包含该文字的元素
- **角色**：`role=button[name="Submit"]` — ARIA 角色匹配

## 批量验收模式

```python
from engine_adapter import Kitewright

pages = [
    {
        "name": "01_首页",
        "url": "http://127.0.0.1:5173/",
        "wait_for": ".app-loaded",
        "asserts": [
            {"text": "仪表盘", "should_exist": True},
            {"text": "Error", "should_exist": False},
        ],
        "screenshot": True,
        "check_console_errors": True,
    },
    {
        "name": "02_数据源",
        "url": "http://127.0.0.1:5173/data",
        "wait_for": "[data-testid='source-list']",
        "asserts": [{"text": "MySQL", "should_exist": True}],
        "screenshot": True,
    },
]

    with Kitewright() as browser:
    results = pilot.verify_pages(pages)
    # → PASS/FAIL 汇总 + 截图存到 /tmp/kitewright/screenshots/
```

## 会话状态持久化

```python
# 首次：完成登录
with Kitewright() as pilot:
        browser.navigate("https://example.test/login")
        browser.type_text("input[name='username']", "test-user")
        browser.type_text("input[name='password']", "test-password")
        browser.click("button[type='submit']")
        browser.wait_for(text="仪表盘")
        state = browser.save_state()
    # state → {"cookies": [...], "localStorage": {...}, "url": "..."}

# 后续：免登录复用
    with Kitewright() as browser:
        browser.restore_state(state)
        browser.navigate("https://example.test/dashboard")
    # 已登录态
```

## Shadow DOM 穿透 — 重要边界

### snapshot 可以穿透（只读）

`snapshot` 工具通过无障碍树（Accessibility Tree）直接穿透 Shadow DOM（包括 `<micro-app>` 微前端架构），**只读取**，不需要手动注入 JS。

```
# 传统 CDP 方式（需要手动注入 JS 穿透 shadowRoot）
# Kitewright 方式：
pilot.navigate("https://store.weixin.qq.com/shop/goods/list")
tree = pilot.snapshot()  # 直接拿到 Shadow DOM 里的完整文本内容
```

### click / extract 无法穿透（CSS 选择器）⚠️

**这是最大的坑**：`click`、`extract`、`fill_form` 等基于 CSS 选择器的工具**无法穿透 Shadow DOM 边界**。即使 `snapshot` 能看到 Shadow DOM 内的元素文字，用 `click("link 草稿箱")` 仍然会返回 False，因为 CSS 查询被 shadow root 阻断。

> **实测**：微信小店商品列表页，`snapshot()` 返回 3499 字符的完整无障碍树（含"草稿箱"链接），但 `click("link 草稿箱")` → `False`。

### 变通方案：URL 参数 / 键盘导航

当目标操作被困在 Shadow DOM 里时：

1. **URL 参数切换**（首选）— 找到目标操作的 URL 参数，直接导航过去。
   ```python
   # 不用 click("link 草稿箱")，直接用 URL 参数切到草稿箱 tab
   pilot.navigate("https://store.weixin.qq.com/shop/goods/list?currentTab=PRODUCT_STATUS_EDIT")
   pilot.wait_for(text="编辑中")  # 等草稿箱内容渲染
   tree = pilot.snapshot()        # 11990 字符，30 条商品全部可见
   ```

2. **键盘导航** — `press_key("Tab")` 逐个聚焦再 `press_key("Enter")`，键盘焦点可以穿越 shadow boundary。

3. **JavaScript 直通** — 用 `call_raw` 执行手写 JS 穿透 `shadowRoot`（最后手段）。

## 嵌入其他系统

### 方式 1：MCP Server 模式（推荐）

kite 作为独立 MCP Server 运行，任何 MCP 客户端直接连接：

```bash
# HTTP 模式（多客户端 + 认证）
bin/kite
# → http://localhost:8090/mcp

# stdio 模式（Claude Code / Cursor / WorkBuddy）
bin/kite --stdio
```

### 方式 2：Python SDK 模式

```python
from engine_adapter import Kitewright

with Kitewright() as pilot:
    pilot.navigate("http://localhost:5173")
    pilot.screenshot("/tmp/page.png")
    result = pilot.assert_text("仪表盘")
```

### 方式 3：HTTP API 模式（MCP Streamable HTTP）

⚠️ **kite 使用 MCP Streamable HTTP 协议，不是普通 JSON-RPC**。直接 POST `tools/call` 会返回 400 错误。必须先握手拿 session-id：

```bash
# 第 1 步：initialize 握手 → 拿到 mcp-session-id
SESSION_ID=$(curl -s -D - -o /dev/null -X POST http://localhost:8090/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"1.0"}}}' \
  | grep -i 'mcp-session-id' | awk '{print $2}' | tr -d '\r\n')

# 第 2 步：后续所有请求都带 session-id + SSE Accept 头
curl -X POST http://localhost:8090/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"browser_navigate","arguments":{"url":"http://localhost:5173"}}}'
```

> **engine_adapter.py 已封装了完整的握手逻辑**（`_init_session` + `call_tool`）。只有自己写 HTTP 客户端时才需要手动处理 session-id 和 SSE 解析。

### 方式 4：AOS Plugin Manifest 模式

作为 AOS 平台的 `kind=browser, runtime=sidecar` 插件安装（位于 `plugins/browser/kitewright/`）。

## 自包含性

本插件**不依赖 kitewright 源码目录**。核心文件：

```
kitewright/
├── bin/
│   └── kite              # 内置 kite 二进制（arm64 Mach-O, 12MB）
├── engine_adapter.py     # Python SDK（Kitewright 类）
├── SKILL.md              # 本文件
├── manifest.json         # AOS 插件清单
└── demo.py               # 演示脚本
```

唯一外部依赖：**系统已安装的 Chrome / Chromium**。

## 与 kitewright 源码目录的关系

- `kitewright/` 目录：Kitewright 的 Rust 源码仓库，仅在**重新编译 kite 二进制**时需要
- `kitewright/bin/kite`：已编译的 kite 二进制副本，运行时独立，不回读源码
- 升级 kite：在 kitewright 目录 `cargo build --release` → 复制到 `bin/kite` → 完成

## 常见坑

| 问题 | 原因 | 解决 |
|------|------|------|
| 端口 8090 被占 | 上次 kite 未正常退出 | `pkill -f "kite"` |
| 页面空白 | SPA 未渲染完 | 用 `wait_for(selector=...)` 而非 sleep |
| 元素找不到 | Shadow DOM 隔离 | 用 `snapshot()` 拿无障碍树穿透 |
| 截图全白 | headless 模式字体缺失 | 安装系统字体或用 headed |
| 状态恢复失败 | cookies 过期 | 重新走登录流程 + save_state |
| kite 无法启动 | 非 arm64 平台 | `npx -y @kitewright/mcp` 替代，或交叉编译 |
| Chrome 未找到 | 未安装 Chrome | 安装 Google Chrome 或 Chromium |
| **HTTP 直接调 tools/call 报 400** | 缺 MCP 握手 | 先 `initialize` 拿 `mcp-session-id`，后续请求带头 + `Accept: application/json, text/event-stream` |
| **snapshot 能看到但 click 返回 False** | CSS 选择器被 Shadow DOM 阻断 | 用 URL 参数直接导航，或键盘 Tab 导航，或 JS 穿透 `shadowRoot` |
| **每次会话都要重新登录** | kite 默认用临时 Chrome 配置目录 | 首次登录后 `save_state()`，后续会话开头 `restore_state(state)` |
| **多实例端口冲突？** | — | **不会**：MCP 用 stdio 管道（无端口），CDP 端口由 kite 动态分配，零冲突 |
| **强风控站点停在 `Please wait...`** | 独立临时 Profile 或自动化环境可能触发前置挑战；本次现场观察到 `navigator.webdriver=true` | 停止，不绕过挑战；需要现有登录态时改用 `control-existing-chrome` 操作用户普通 Chrome |

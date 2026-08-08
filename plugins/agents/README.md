# Agent Plugins

对齐 20 §3.1 / 方案 98。

Agent 插件是可执行的智能体能力包，以 sidecar 进程形式运行，通过 MCP/HTTP/CDP 协议与 Host 交互。

## 当前插件

| 插件 | 版本 | 引擎 | 内置二进制 | 说明 |
|------|------|------|-----------|------|
| `browser-pilot` | 0.2.0 | Kitewright MCP | `bin/kite` (12MB, arm64) | 原生 CDP 浏览器自动驾驶 — 导航/截图/点击/输入/断言/无障碍树/控制台/网络/PDF |

## 插件结构

```
agents/
└── browser-pilot/
    ├── bin/
    │   └── kite              # 内置 kite 二进制（arm64 Mach-O）
    ├── manifest.json          # 插件清单（AOS 标准格式）
    ├── SKILL.md              # AI Agent 技能定义（调用时机、工具说明、使用示例）
    ├── engine_adapter.py     # Python SDK（BrowserPilot → KitewrightMCP）
    └── demo.py               # 演示脚本
```

## 自包含性

Browser Pilot **不依赖 kitewright 源码目录**。kite 二进制已内置在 `bin/` 下。

- 运行时：只用 `bin/kite` + 系统 Chrome
- 升级 kite：`cd kitewright && cargo build --release -p kitewright && cp target/release/kite aos-platform/plugins/agents/browser-pilot/bin/kite`
- 跨平台：非 arm64 需重新编译或用 `npx -y @kitewright/mcp` 替代

## manifest.json 格式

```json
{
  "id": "browser-pilot",
  "kind": "agent",
  "runtime": "sidecar",
  "version": "0.2.0",
  "capabilities": ["navigate", "screenshot", "click", ...],
  "healthPath": "/v1/agents/browser-pilot/health",
  "configSchema": { ... }
}
```

## 新增 Agent 插件

1. 复制 `browser-pilot/` 目录 → 改 `id`
2. 修改 `manifest.json` 的 `capabilities` 和 `configSchema`
3. 编写 `SKILL.md`（调用时机 + 工具说明）
4. 实现引擎适配器（`engine_adapter.py`）
5. 安装到 Host

## 移植到其他系统

Browser Pilot 的设计是**系统无关**的：

1. **MCP 模式**：`bin/kite` 直接启动为 MCP Server，任何 MCP 客户端（Claude Code / Cursor / WorkBuddy）直接连接
2. **Python SDK 模式**：`from engine_adapter import BrowserPilot`，3 行代码操控浏览器
3. **HTTP API 模式**：通过 `http://localhost:8090/mcp` 调用 MCP JSON-RPC
4. **AOS Plugin 模式**：作为 `kind=agent, runtime=sidecar` 插件安装

核心依赖只有：**Chrome 浏览器** + **bin/kite**。不需要 Rust、Node.js、Playwright、Selenium 或任何扩展。

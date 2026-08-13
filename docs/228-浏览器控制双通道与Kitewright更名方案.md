# 浏览器控制三种会话模式与 Kitewright 更名方案

## 1. 目标

1. 将 `plugins/browser/browser-pilot` 正式更名为 `plugins/browser/kitewright`，让插件名与真实引擎一致。
2. 明确 Kitewright 是“独立启动专用 Chrome/Chromium”的自动化通道，不等同于复用用户当前普通 Chrome。
3. 新增 `control-existing-chrome` Skill，沉淀复用已打开、已登录普通 Chrome 的合规操作方法。
4. 记录本次掘金发布的成功链路、失败链路、证据边界与故障恢复方法，供 Codex、WorkBuddy、Trae Work 等工具复用。
5. 当前 `control-existing-chrome` 实现边界固定为 macOS；Windows 和 Linux 尚未实现、未验证，不属于本 Skill 的支持范围。
6. 新增 `control-dedicated-chrome` Skill，在 macOS 上启动一个使用独立持久 Profile 的普通 Chrome，避免改动用户日常 Chrome 的标签页和 Profile。

## 2. 已核验事实

### 2.1 Kitewright 源码事实

- `kitewright/crates/engine/src/lib.rs` 每次启动生成独立临时 `user_data_dir`。
- Kitewright 自行启动 Chrome/Chromium，并加入 `no-sandbox`、`disable-extensions`、`disable-sync`、`no-first-run` 等参数。
- 默认是有界面的 headed 浏览器；设置 `KITE_HEADLESS` 后进入 headless。
- 该模式不复用用户普通 Chrome 的现有 Profile、标签页和登录上下文。

### 2.2 本次掘金现场观察

- Kitewright 启动的专用 Chrome 访问掘金创作者中心时，页面停留在 `Please wait...` 前置挑战。
- 页面环境只读检查观察到 `navigator.webdriver=true`。
- 未尝试破解挑战、伪造浏览器指纹或自动处理验证码。
- 切换到用户已经登录的普通 Chrome，并通过 macOS 可视化/无障碍控制后，可以正常编辑、提交和在文章管理页核验状态。

以上仅是本次运行和当前构建的真实观察，不宣称为掘金官方审核规则，也不宣称所有 Kitewright 版本、所有网站都会出现相同行为。

## 3. 三种会话模式的职责

### 3.1 `kitewright`

适合：

- 本地页面验收；
- 批量 E2E；
- 无障碍树、Shadow DOM 读取；
- 控制台与网络捕获；
- 截图、PDF、确定性自动化。

限制：

- 启动独立 Chrome/Chromium 和独立临时 Profile；
- 不天然拥有用户普通 Chrome 的登录态；
- 自动化环境可能被强风控站点识别；
- 遇到前置挑战、验证码或风险验证必须停止，不得规避。

### 3.2 `control-existing-chrome`

平台边界：

- 当前版本仅支持 macOS；
- 已验证的主控制面是 macOS Computer Use、Accessibility 或等价系统级可视化控制；
- Windows UI Automation、Windows Computer Use 与 Linux 辅助功能控制尚未实现和验证；
- 在 Windows 或 Linux 上触发时，必须停止并报告“当前 Skill 仅支持 macOS”，不得自行假设兼容。

适合：

- 必须使用用户当前登录态；
- 登录站点对独立自动化浏览器兼容性较差；
- 需要操作用户已打开标签页；
- 需要普通 Chrome 的真实可视页面行为。

优先实现方式：

1. macOS Computer Use、Accessibility 或等价系统级可视化控制；这条路径可直接复用用户已打开、已登录的普通 Chrome，不需要安装 Chrome 扩展；
2. 工具已经提供的原生 Chrome 连接仅作为可选控制面，不是 Skill 的前置条件；
3. 只有 Chrome 已由用户明确以远程调试模式启动时，才考虑 CDP Bridge。

该通道不得读取、复制或导出 Cookie、Token、密码、Local Storage；不得把普通 Profile 复制到自动化 Profile。

### 3.3 `control-dedicated-chrome`

适合：

- 希望使用持久登录态，但不改动用户日常 Chrome Profile；
- 希望为发布、运营或验收建立一个可见、可接管的专用普通 Chrome；
- 不希望使用 Kitewright 的临时自动化 Profile。

实现边界：

- 当前版本仅支持 macOS；
- 通过 Google Chrome 官方应用启动一个新进程，使用独立 `--user-data-dir`；
- 默认持久 Profile 位于用户的 `~/Library/Application Support/AOS Dedicated Chrome`，不纳入 Git；
- 首次由用户在该专用窗口内手动登录，后续可复用该专用 Profile 的登录态；
- 不复制用户主 Profile、Cookie、Token 或密码；
- 只使用普通 Chrome 启动参数，不隐藏 WebDriver，不规避风控。

隔离效果与限制：

- 专用 Profile 可以隔离账号、历史、扩展、标签页和站点会话；
- 不会改动用户日常 Chrome 的标签页；
- macOS 可视化控制仍可能切换前台窗口或占用鼠标、键盘焦点，因此只能降低干扰，不承诺“后台无感控制”。
- 日常 Chrome 和专用 Chrome 可能共享 `com.google.Chrome` Bundle ID；如果 Computer Use/Accessibility 无法明确区分两个进程或窗口，后续自动操作必须停止，不得根据应用名或 Bundle ID 猜测目标。

## 4. 迁移与兼容策略

### 4.1 目录与标识

- 目录：`plugins/browser/browser-pilot` → `plugins/browser/kitewright`
- Skill 名：`browser-pilot` → `kitewright`
- Manifest ID：`browser-pilot` → `kitewright`
- 健康检查路径：`/v1/browser/browser-pilot/health` → `/v1/browser/kitewright/health`
- 截图默认目录：`/tmp/browser-pilot/screenshots` → `/tmp/kitewright/screenshots`

### 4.2 Python 兼容

- 新主类命名为 `Kitewright`。
- 暂时保留 `BrowserPilot = Kitewright` 兼容别名，避免已有 Python 调用立即失效。
- 新文档和示例统一使用 `Kitewright`。

### 4.3 仓库引用

- 更新受版本控制且会因目录迁移失效的导入路径。
- 不改动本次范围外的未提交验证脚本和历史证据。

## 5. 新 Skill 结构

```text
plugins/browser/control-existing-chrome/
├── SKILL.md
├── agents/openai.yaml
└── references/
    └── 普通Chrome可视化控制与掘金发布实践.md

plugins/browser/control-dedicated-chrome/
├── SKILL.md
├── agents/openai.yaml
└── scripts/
    └── launch_dedicated_chrome.sh
```

Skill 只保存核心选择、操作和安全规则；详细现场、恢复步骤和证据边界放入 reference。

## 6. 验收

1. 两个 Skill 均通过 `quick_validate.py`。
2. `manifest.json` 可被 JSON 解析。
3. `engine_adapter.py` 可编译，`Kitewright` 与 `BrowserPilot` 均可导入且为同一实现。
4. 新目录中不存在旧的自我标识和旧健康检查路径。
5. 全仓库受版本控制文件不存在指向已删除 `plugins/browser/browser-pilot` 的有效运行时引用。
6. 实践文档明确区分源码事实、现场观察、有限推断和未知平台规则。
7. Skill 在元数据、正文和界面描述中均明确标记“仅支持 macOS”，Windows/Linux 不会被误路由到本实现。
8. 专用 Chrome 启动脚本可重复启动同一持久 Profile，且不使用用户主 Chrome Profile。
9. 首次登录验收只由用户输入账号、密码和验证码；验收时只确认专用窗口已进入登录后页面，不读取凭据。
10. “专用 Chrome 可启动且用户完成登录”与“自动化工具可安全精准选中专用窗口”是两个独立验收项，不得用前者替代后者。

## 9. CDP Bridge 强风控站点实验方案

### 9.1 实验目标

验证以下命题，不预设结论：

1. Chrome 仅绑定本机 CDP 端口时，不需要 Chrome 扩展；
2. 指定非零远程调试端口的实际页面中，`navigator.webdriver` 的现场取值；
3. 掘金创作者中心是否出现前置挑战，以及用户是否可手动登录；
4. 登录后 CDP 是否能精准操作任务专属页签，不依赖 macOS Bundle ID 区分 Chrome 进程；
5. 经用户授权后，是否能完成一篇脱敏文章的提交与管理页状态核验。

### 9.2 隔离与安全边界

- 使用独立端口 `9224`，不复用 `9222/9223`；
- 使用独立持久 Profile `~/Library/Application Support/AOS CDP Chrome 9224`；
- CDP 只绑定 `127.0.0.1`，不对局域网或公网暴露；
- 不复制主 Profile、Cookie、Token、密码或 Local Storage；
- 登录、验证码、扫码和风险确认由用户手动完成；
- 不隐藏或修改 `navigator.webdriver`，不伪造指纹，不规避挑战；
- 只枚举和操作实验专属的掘金页签，不报告无关页签。

### 9.3 文章发布边界

原稿 `/Users/ddt/work/projects/ai_agent/智能体记忆与协作整体方案.md` 不能原样公开，因其包含本机路径、认证配置位置、内部工具状态和已知密钥风险描述。实验发布版必须：

- 保留“多对话共享一份可审计事实”的核心方法；
- 删除真实用户名、本机绝对路径、凭据位置、内部服务状态和项目私有数据；
- 不将任何平台审核小样本写成官方规则；
- 提交后只把创作者中心管理页状态作为结论。

### 9.4 成功门槛

只有以下条件全部成立，才在仓库新增 `plugins/browser/cdp-bridge` Skill：

1. `9224` 本地端口可稳定连接；
2. 现场记录 `navigator.webdriver` 真实值；
3. 用户能在专用 Chrome 中完成掘金登录；
4. CDP 能按 URL 精准锁定专属页签；
5. 脱敏文章成功提交，并在管理页读到权威状态；
6. 实验期间没有读取凭据、绕过风控或误操作无关页签。

Windows 支持只在工作流层面声明：CDP 连接和操作流程可跨平台，但 Chrome 可执行文件路径、Profile 路径、进程管理与端口防火墙必须为 Windows 单独实现和验证，不使用 macOS 成功代替 Windows 实测。

### 9.5 2026-08-12 实验结果：CDP 连接成功，掘金强风控兼容失败

实验环境：

- Google Chrome `151.0.7922.109`；
- 本地调试端口 `127.0.0.1:9224`；
- 独立持久 Profile `~/Library/Application Support/AOS CDP Chrome 9224`；
- 目标页面为掘金创作者中心文章管理页。

已观察事实：

1. Chrome DevTools Protocol 端点可正常连接，协议版本为 `1.3`；
2. 连接过程不需要 Chrome 扩展；
3. 目标页面实测 `navigator.webdriver === false`；
4. 即使如此，页面仍持续显示 `Please wait...`，未进入掘金登录流程；
5. 用户可见截图与 CDP 读取到的页面文本一致；
6. 未尝试隐藏 WebDriver、修改指纹、解题、自动验证或其他规避手段。

有限推断：

- `navigator.webdriver=false` 不是通过掘金前置风控的充分条件；
- 站点可能结合新 Profile、启动参数、浏览器环境、网络、会话或其他未知信号，但本次实验不能确定具体原因和权重；
- 不能因为 CDP 无需扩展、且 `webdriver=false`，就宣称它适合所有强风控登录站点。

本次结论：

- CDP Bridge 作为本机浏览器传输和精确页签控制方式，技术连接验证通过；
- CDP Bridge 在本次掘金强风控登录场景中验证失败；
- 未达到第 9.4 节的全部成功门槛，因此不发布实验文章，不在仓库新增 `plugins/browser/cdp-bridge` Skill；
- 该结论只适用于本次 Chrome 版本、启动方式、新独立 Profile 和掘金页面，不扩大为 CDP 或其他平台的官方规则。

## 7. 风险与回滚

- 风险：外部脚本仍硬编码旧目录。缓解：保留类兼容别名，并通过全仓库检索暴露剩余引用。
- 风险：把普通 Chrome 控制误解为反检测工具。缓解：Skill 明确禁止绕过挑战、验证码和指纹检测，只允许操作用户授权的现有会话。
- 回滚：目录和标识可恢复为旧名；新 Skill 独立，不影响 Kitewright 运行时。

## 8. 实施结果与验证

本次已按本方案完成：

- 原 `plugins/browser/browser-pilot` 已迁移为 `plugins/browser/kitewright`；
- 主类更名为 `Kitewright`，保留 `BrowserPilot = Kitewright` 兼容别名；
- 新增 `plugins/browser/control-existing-chrome` Skill，用于合规复用已打开、已登录的普通 Chrome；
- 已同步 Manifest ID、健康检查路径、截图目录、演示脚本与受版本控制的调用路径。

验证结果：

- `control-existing-chrome` 和 `kitewright` 均通过 `quick_validate.py`；
- `manifest.json` 通过 JSON 解析；
- `engine_adapter.py`、`demo.py` 和 `scripts/d5e2_browser_verify.py` 通过 Python 编译检查；
- `Kitewright` 与 `BrowserPilot` 兼容别名是同一实现；
- 受版本控制的运行时文件中，不再存在指向旧目录的有效引用；
- `git diff --check` 通过。

证据边界：Kitewright 源码能证明它使用独立临时 Profile 并自行启动 Chrome/Chromium；源码未显式传入名为 `webdriver=true` 的 CLI 参数。2026-08-12 掘金现场可观察到的是 `navigator.webdriver === true` 且页面停留在 `Please wait...`。两者不得混为同一条源码事实，也不将该单次现象写成掘金官方规则。

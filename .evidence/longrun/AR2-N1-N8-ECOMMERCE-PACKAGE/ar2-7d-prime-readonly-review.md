# AR2-7D Prime 独立只读终审

日期：2026-09-10  
审查目标：`m1@e4aa1534`  
Prime provider：`github-copilot`  
Prime model：`gpt-4.1`（Copilot Free 当前实际可调用的 chat endpoint）  
结论：`VERDICT: PASS`

## 1. 执行边界

- 依据 `231-6-串行施工包与双目标联合验收实施方案.md` 第 160、276 条，在 7D authority CAS 和进入 7E 前执行 Prime 独立只读复审。
- Prime 使用 `--no-tools --no-session --no-context-files`，只读取显式附加的 231-6、closure manifest、动态阶段定义、7D 方案/验证/独立 Codex 复核以及受影响源码和测试。
- 审查期间文件修改、Provider 业务调用、真实业务 mutation、生产迁移、外部发布和 push 均为 0；`230 L0` 继续挂起。
- OAuth 凭据只由 Prime 的 `AuthStorage` 持久化；本文不记录设备码、access token、refresh token 或其他秘密。

## 2. 登录与模型路由诊断

- GitHub device flow 已由用户在同一 `datong838` 账户显式批准，`~/.prime/agent/auth.json` 中新增 `github-copilot` provider 登录态。
- 首两次批准后的 token exchange 因终端未继承 macOS 系统代理而 `fetch failed`；确认浏览器使用 `127.0.0.1:7897` 后，Prime 通过同一本机代理完成登录并输出 `LOGIN_RESULT=success`。
- Prime 本地目录列出的 `gpt-6-astra`、`gpt-5.3-codex`、`gpt-5-mini` 与当前 Copilot Free inference entitlement 不一致。通过已授权 `/models` 只读目录和最小无仓库提示验证，当前账户实际可调用 `gpt-4.1` chat endpoint；隔离 `/tmp` 模型登记验证返回 `OK` 后才执行正式审查。
- 临时模型登记与认证副本位于 `/tmp`，未修改 `prime-agent` 仓库的既有脏文件或全局模型配置。

## 3. Prime 判定原文要点

Prime 首行输出：

> VERDICT: PASS

Prime 核查结论：

1. 生产 Router manifest 和生成聚合只登记 `aos_api.routers.extension_dispatch`，旧电商 Router 不再直接登记。
2. `extension_dispatch.py` 只组合历史 GET/HEAD 只读投影与一个参数化 Canonical POST；历史 POST/PUT/PATCH/DELETE 不进入生产有效路由，入口没有领域 SQL 或旁路写 Handler。
3. Canonical POST 只接受九个固定 `operation_id`，继续通过 `EcommerceGrowthCanonicalRouter` 执行租户、权限、DispatchRef、fence、generation、epoch 与 Receipt 边界。
4. Web `/workshop/*` 只进入 `EcommerceWorkshopHost`；旧 orders/inventory 深链仅在当前安装目录声明 `legacyRoutes` 时兼容，静态导航已隐藏。
5. `InstalledModuleNavigation` 只遍历 `catalog.modules`；空目录、403、读取失败与未安装态不会泄漏旧链接或伪造模块能力。
6. Router、manifest、Web 正反测试和验证证据与冻结方案一致，没有阻止 7D authority CAS 或进入 7E 的代码缺陷。

Prime 记录的非阻断限制：历史 Router 源文件继续保留用于只读投影和历史测试；新增历史写方法将由专项测试阻断；八页三视口和完整交互仍属于 AR2-7E，不能由本次 7D PASS 提前宣称完成。

## 4. 退出判断

- Prime 独立只读复审门：PASS。
- 7D 代码、累计回归、资产控制浏览器、closure 与 Prime 复审已闭合，可继续执行独立 authority CAS。
- 本文件本身不写 authority；只有主执行器按当前 authority、Task、Lease 和 CAS 规则完成前推后，才允许进入 7E。

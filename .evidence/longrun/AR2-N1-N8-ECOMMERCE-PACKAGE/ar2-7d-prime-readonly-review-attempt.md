# AR2-7D Prime 独立只读复核尝试记录

日期：2026-09-10 06:14 +0800  
基线：`m1@46fe1776e6c50c9ab6043ed7236a5bbeb609d5d1`  
状态：`BLOCKED_EXTERNAL_AUTH_NOT_A_REVIEW_VERDICT`

## 1. Rules

- 按 231-6 第 160、276 条，AR2-7D 在进入 7E 前必须完成 Prime 独立只读复核；Prime 不写业务代码、authority 或并行业务分支。
- 复核输入只包含已提交的 7D 方案、验证证据、closure manifest、动态阶段 JSON、生产 Router/Web 入口和对应测试；运行时关闭工具、会话保存和上下文文件加载。
- 不复制、打印或改写任何凭据；认证失败不得伪造为 PASS，也不得据此前推 authority。

## 2. 恢复与调用

1. 系统重启后，Prime 源仓的构建产物缺失；使用本机已有依赖完成 `tui`、`ai`、`agent`、`coding-agent` 构建。Prime 仓原有 `package-lock.json`、`packages/ai/src/models.generated.ts` 和未跟踪文档保持在原状态范围，不纳入 AOS 提交。
2. 使用 Node `v24.19.0` 验证 Prime CLI 可启动，后台服务状态可读取。
3. 以 `--no-tools --no-session --no-context-files` 注入 7D 复核包，要求核对 Canonical POST 唯一性、legacy 写路由不可达、GET/HEAD 保留、`catalog.modules` 唯一导航来源、证据一致性和 no-effect 边界。
4. 默认提供方返回 `401 无效的令牌`；显式 `openai-codex` 提供方返回 `No API key found for openai-codex`。两次均在生成任何审查正文之前结束。
5. 用户随后明确要求继续 Loop，并授权上一条已说明的 Prime ChatGPT OAuth 登录。浏览器使用既有登录会话完成 workspace 选择和 consent，回调页显示认证流程完成；Prime 在 token exchange 阶段收到 `403 unsupported_country_region_territory`，未写入 `openai-codex` 凭据，仍未生成审查正文。记录中不保存授权码、token、邮箱或其他认证材料。
6. `m1@9e6734b6` 关闭独立 Codex 首轮发现后，再次枚举 Prime model：当前只暴露 AGnes 的三个模型，认证文件也只有 `agnes` provider。使用 `agnes-2.5-pro` 和同一 `--no-tools --no-session --no-context-files` 只读包新鲜重试，仍在生成审查正文前返回 `401 无效的令牌`；未修改认证文件，未尝试未经授权的其他 OAuth provider。
7. 用户对明确的 GitHub Copilot OAuth 问题回复继续开发并要求 Loop，主执行器据此启动 `github.com` device flow。现有 Chrome 会话没有可复用的 GitHub 登录态；选择现有 Google 会话后进入 GitHub 新账户注册，而不是已有账户登录。创建外部账户不在本次授权内，流程在注册前停止；Prime 认证文件仍只有 `agnes`，本机常见 Provider 环境变量、GitHub CLI、AWS 与 gcloud 均没有可复用登录态。证据不保存 device code、邮箱或任何凭据。

## 3. 结论与处置

- 本记录不是 Prime 复核结论；没有 `VERDICT: PASS` 或 `VERDICT: BLOCK` 可引用。
- 7D 代码与确定性验证仍保持通过：`verify_closure.py --phase ar2-7` 为 1711 scanned / 93 classified / 57 migrated，五类错误为空；memory validate 为 GREEN；隔离 PostgreSQL 容器可用。
- 由于 231-6 明确把 Prime 复核列为 7D 退出条件，当前不写 `AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN` authority CAS，也不把 7E 记为已进入。
- 下一动作固定为由用户在现有 Chrome 登录一个已有且具备 Copilot 权限的 GitHub 账户，或另行提供合法可用的 Prime provider 登录态，然后重放同一只读复核包；现有 AGnes、ChatGPT OAuth 和无账户的 GitHub device flow 均已穷尽。认证恢复前只允许整理 7E 输入与确定性只读检查，不修改 7E 产品代码。独立 Codex 只读复核可作为缺陷扫描补充，但不得冒充 Prime PASS 或解除 231-6 门禁。

## 4. 外部效果

- Provider 业务调用：0。
- 真实业务 mutation：0。
- 生产迁移、外部发布、push：0。
- `230 L0`：继续挂起。

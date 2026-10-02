# 2026-10-02 最新 m1@df5a0d5b 权威卷完整重启复验

结论：`CURRENT_LATEST_PREVIEW_STACK_RESTART_GREEN`，范围仅为本机禁入预览栈。按 231-3/231-5、既有 118→135 迁移重启方案和用户最新授权执行。本次代码无新 migration；未迁移、切库、删卷或启 Host。正式受限身份/八配置/自然首链仍未通过。

| 门 | 实测证据 |
|---|---|
| 代码/工作树 | `git rev-parse --short HEAD`=`df5a0d5b`；m1 单写。浏览器插件/pnpm 等既有脏文件及 test-only 未跟踪文件未碰；本波只新增本验证。代码头、当前库 `a0v_135`；`a0v_current_preview_http.py` 签名 preflight 回 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`、`database=aos_current_preview_20260927`、`codeVersion=version=a0v_135`、approved 安装和 published4、binding0。 |
| 卷/备份 | `docker --context colima-aos-extension inspect aos-a0v-recovery-pg` 当前仍挂 `aos-a0v-recovery-pg-data:/var/lib/postgresql/data`；当日独立停机备份 `aos-recovery/.aos-current-backup-20261002-cutover135/current.dump` SHA256=`8862e763347caae6c9f9ce1e15aac3e906e6770aa3c53a95bda33678863d8188`；`docker ... exec -i ... pg_restore -l < current.dump` 退出0。其118→135全库独立恢复演练证据见 `w5cb4-daily20261002-current-118to135-restart-verification.md`。 |
| 零执行/重启次序 | `launchctl bootout` Web、API 各退出0；8080/8434/18181 均无监听，当前库其他 client backend=0。`docker --context colima-aos-extension restart aos-a0v-recovery-pg`退出0，PG启动 `2026-10-02T03:28:57Z`、`pg_isready`接受连接；再次签名 preflight GREEN。随后 `launchctl bootstrap` API、Web 各退出0。API PID34074 本地11:29:28、Web PID34131 11:29:48，均晚于 `df5a0d5b` 提交及 PG 重启。 |
| 端口/健康 | 18435/8080/8434 LISTEN；18181 无监听。`curl` API `/v1/health`、`/v1/ready`、`/openapi.json` 及八 `/workshop/{cockpit,content-campaign,operations,creator-growth,media-studio,analyst,price-governance,customer}`、`/aip/skill-publish`、`/aip/agent-catalog` 全为200/退出0。API 日志最新 `CURRENT_PREVIEW_HTTP_STARTING` 为 `migrationMode=disabled,runtimeHost=0,workersEnabled=0`，`startup_extension_runtime_host_inactive code=DISABLED`。 |
| 浏览器/隔离 | Codex 浏览器逐页打开八工作台，等目录加载后八页均显示“当前工作台入口不可用”；技能发布页37仅已评测、已发布0、三来源阻断、发布按钮 disabled、导航无可见电商入口。当前库只读回读：正租户安装 `approved/revision3/active NULL`，binding0、Host assignment0、Host identity0、runtime command receipt0；`dev-org`安装0。八类当前配置候选全0。浏览器停留 `/aip/skill-publish`。 |

限制：当前 API 仍由旧 `--serve` 本机预览启动，日志显示 `allow_dev=1`；它只用于禁入质量检查，不能作为正式受限 API 或当前业务权限证明。外部 OIDC、独立 API/目录/Web/Host 身份、八配置、Growth1.13 当前正式发布、assignment/binding 和真实首链仍待补。未读商城源、未写 dev-org、未重放旧12 Run、未手工 run_definition、未触发 Provider/业务外部效果、未 push。

下一研发入口：GW-b-2c2c1b3c2d2b2 宿主生成 v3 exact 原 Owner/Receipt RED；正式身份来源另门并行只读对账。

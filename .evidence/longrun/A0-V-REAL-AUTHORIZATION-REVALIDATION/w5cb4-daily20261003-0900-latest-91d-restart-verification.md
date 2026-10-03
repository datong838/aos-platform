# 2026-10-03 当日最新 m1/权威卷完整重启验收

依据 231 长程路线、当日完整重启方案 `w5cb4-daily20261003-post-reboot-latest-restart-plan.md`、用户授权及 `AOS-001199`。范围为本机禁入预览栈；正式受限 API、Host/worker/Provider 与首链另门。

| 检查 | 命令/结果 |
|---|---|
| 单写与代码/数据 | `git log -1 --oneline` → `91d791dd`（m1），代码唯一 Alembic 头 `a0v_135`；`docker --context colima-aos-extension inspect aos-a0v-recovery-pg` 回运行容器和原命名卷 `aos-a0v-recovery-pg-data`；`psql ... SELECT current_database(),version_num FROM alembic_version` → `aos_current_preview_20260927|a0v_135`，exit0。未动其他分支/未 push；仓中非本任务的 browser plugin dirty files 保留。 |
| 独立备份/正式安装来源 | 当日独立全量 `/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-current-backup-20261003-post-reboot-135/current-full.dump` SHA256 `e2c3a4b6881e5b4616b92ce42052227d6a20fa34b4310debcda83c939c9e04a0`，容器 `pg_restore -l` exit0、TOC 5905 行。`a0v_current_preview_http.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json` 重启前后 exit0：`CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`、approved 安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813`、publishedVersions4、runtimeBindings0。没有新做全库恢复演练。 |
| 顺序重启 | `launchctl bootout gui/501/com.aos.a0v-web-8434` 与 `...api-daily0900` exit0，8080/8434/18181 均 CLOSED；`docker --context colima-aos-extension restart aos-a0v-recovery-pg` 成功，StartedAt=`2026-10-03T01:02:50.910615408Z`、原卷不变。紧接的一次 `pg_isready` 因冷启动 exit2，有限重试后 accepting/版本135 exit0。签名预检再次 GREEN 后原 plist `launchctl bootstrap` API/Web exit0，新 PID 47438/47441。 |
| 端口/页面/安全门 | 18435/8080/8434 LISTEN、18181 CLOSED。`/v1/health`、`/v1/ready`、`/openapi.json`、八 `/workshop/{cockpit,content-campaign,operations,creator-growth,media-studio,analyst,price-governance,customer}`、`/aip/{skill-publish,agent-catalog}` HTTP 全200，命令 exit0；最新 API 日志 `migrationMode=disabled,runtimeHost=0,workersEnabled=0`、`startup_extension_runtime_host_inactive code=DISABLED`。 |
| 浏览器与只读业务核验 | Codex in-app browser CUA 重载 `/aip/skill-publish`：`org-org/dev-project`，37 仅已评测、已发布0，缺正式技能放行事件、Logic 当前发布版、模型 Route/Policy 三阻断，`发布此修订` disabled，左侧无电商可见入口；`/workshop/cockpit` 见“当前工作台入口不可用”。截图保留在本轮 CUA 工具证据。首次页面加载阶段短暂显示目录/候选读取失败，刷新后稳定。当前库 `BEGIN READ ONLY` 查询 exit0：八类有效配置计数全0，binding/Host assignment/identity/operation 各0。 |

校正记录：主机无 `pg_restore` 可执行文件、容器 `pg_restore -l -` 不接受字面 `-`，改从 stdin 调容器 `pg_restore -l` 后 TOC 验证 exit0。上述错误不代表备份损坏。没有读取商城源、删除库/卷/备份、重放旧 12 Run、手工 run_definition 或启动 Host/worker/Provider。

结论：`CURRENT_LATEST_PREVIEW_STACK_RESTART_GREEN`，仅对本机预览栈与失败封闭有效。API 是现有 `--serve` 预览路径，不证明外部 OIDC/独立正式身份；八配置、Growth 1.13 正式发布、Host Owner/assignment、Binding 和自然首链仍未通过。检查后继续 E17-s3o-o 受限 readiness reader 与原 evaluate 隔离开发，Goal active。

# 2026-10-02 当前权威卷 118→135 与最新栈重启验证

## 结论

**CURRENT_LATEST_STACK_RESTART_GREEN（限本机禁入预览栈）**。`m1@d1af3da8`、原权威命名卷 `aos-a0v-recovery-pg-data` 的 `aos_current_preview_20260927` 已从118迁到代码唯一头135，并重启同一 PG 容器、最新工作树 API/Web。正式受限 API 身份、外部 OIDC、Host/worker/Provider、自然经营首链及八工作台业务入口**未通过**；不以端口/页面200冒充这些门。

## 可复核证据

| 门 | 命令与回读 |
|---|---|
| 权威与零执行窗口 | `git rev-parse HEAD`=`d1af3da8fe041ecd21768bb7555d051f141c4da6`；`docker --context colima-aos-extension inspect aos-a0v-recovery-pg` 挂 `aos-a0v-recovery-pg-data:/var/lib/postgresql/data`；停 API/Web LaunchAgent 后 `lsof` 对8080/8434/18181退出1，当前库其他 client backend=0，版本118。 |
| 第二份停机备份与独立恢复 | 私有目录 `aos-recovery/.aos-current-backup-20261002-cutover135` 为0700，`current.dump` 为0600、3,961,457 bytes、SHA256 `8862e763347caae6c9f9ce1e15aac3e906e6770aa3c53a95bda33678863d8188`；`pg_restore -l`退出0。`rehearse.py` 在独立 test-only PG 新库 `aos_daily_cutover_20261002_135` 全库恢复，旧580表/控制摘要相等，119…135逐步迁移、旧数据不变、schema receipt运行角色 `SELECT=t/INSERT=f`，退出0，`verified.json=FRESH_RESTORE_AND_118_TO_135_CLONE_GREEN`。当日08:54另一独立备份与克隆仍保留。 |
| 当前精确迁移 | 仓外私有 `migrate_current.py` 检查 m1/卷/库/停机端口/源摘要/备份hash/迁移链后执行原 Alembic 119…135，每步事务与 `current-done-*.json` 回读；退出0。`current-cutover-verified.json= CURRENT_118_TO_135_GREEN`，当前 `alembic_version=a0v_135`，原580表旧行及17控制摘要保持，新增12表；`aos_runtime` 对 `extension_schema_installation` `SELECT=t/INSERT=f`。无业务写/Provider调用/Run重发。 |
| 同卷最新栈 | `docker --context colima-aos-extension restart aos-a0v-recovery-pg`退出0；`pg_isready`接受连接，原卷不变。当前签名 Receipt `/Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json` 由 `a0v_current_preview_http.py` 返回 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`，版本/代码135、approved安装1/published4/binding0。API LaunchAgent 新PID26049于10:17:11、Web 新PID26099于10:17:21启动；PG于10:16:41Z重新启动。18435/8080/8434监听、18181无监听；API `/v1/health`、`/v1/ready`、`/openapi.json` 均200。日志 `migrationMode=disabled`、`runtimeHost=0`、`workersEnabled=0`、`startup_extension_runtime_host_inactive code=DISABLED`。 |
| 页面与只读交互 | 8434 八 `/workshop/{cockpit,content-campaign,operations,creator-growth,media-studio,analyst,price-governance,customer}` 与 `/aip/{skill-publish,agent-catalog}` HTTP均200。实际 Codex 浏览器打开八页，均见“当前工作台入口不可用”；技能发布页“刷新”后仍37条仅已评测、已发布0，缺正式发布决定/Logic发布/模型路由策略，按钮 `发布此修订` disabled。浏览器截图已在本轮工具输出展示；浏览器页保留给用户。 |
| 安装与隔离 | 当前库只读 SQL：`org-org/dev-project` 安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813` 为 `approved/currentRevision3/activeRevision NULL/etag3`；`dev-org`安装0、正租户binding0、Host assignment0。 |
| 回归与复审 | `pytest -q services/aos-api/tests/extension_runtime/test_a0v_current_preview_http.py`：13 passed/7 warnings，退出0；`py_compile`当前迁移脚本退出0；`git diff --check`退出0。方案明确的唯一目标/17迁移/停机备份/同卷重启/禁入验证全部逐项对齐。 |

## 风险与下一波

本次沿用已有的本机 `--serve` 预览启动路径；它不是 E17 的受限正式 API 身份，且当前缺可用外部 OIDC 配置。正式独立 API/目录/Web/Host 身份、八配置与Owner、Growth1.13正式信任根及安装仍待证，不能启Host/worker/Provider或声称自然首链。下波先关闭本地预览高权限服务与正式受限启动之间的身份/配置缺口；若外部 OIDC 不在当前配置中，具体正式实例继续失败关闭，转做独立安全研发。保留所有备份、库和卷，不push。

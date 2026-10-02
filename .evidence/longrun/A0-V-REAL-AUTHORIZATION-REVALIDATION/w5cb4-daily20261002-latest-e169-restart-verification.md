# 2026-10-02 15:58 CST 最新 m1 与当前权威卷完整重启复验

范围是本机 **禁入预览栈**，不是正式受限 API/Host 或经营首链放行。起点 `aos-platform/m1@e169e096`、`docs/m1@34f1ff76`、Authority `AOS-001140`；代码改动 `24b5eb76` 已纳入本次进程。m1 单写，原有 browser/pnpm 未提交改动和 test-only/旧截图文件未触碰。

| 门 | 命令与新鲜结果 |
| --- | --- |
| 代码/库迁移 | `git rev-parse --short HEAD`→`e169e096`；`alembic -c services/aos-api/alembic.ini heads`→`a0v_135 (head)`，退出0；权威库 `aos_current_preview_20260927` 只读 `alembic_version`→`a0v_135`，退出0。无新迁移、未切库。 |
| 卷/独立备份 | `docker --context colima-aos-extension inspect aos-a0v-recovery-pg`→命名卷 `aos-a0v-recovery-pg-data:/var/lib/postgresql/data`；`aos-recovery/.aos-current-backup-20261002-cutover135/current.dump` SHA256 `8862e763347caae6c9f9ce1e15aac3e906e6770aa3c53a95bda33678863d8188`；容器内 `pg_restore -l` 退出0。118→135 的独立全库恢复演练见当日 cutover135 verification；本次未再做写入恢复。 |
| 签名/安装来源 | `services/aos-api/.venv/bin/python scripts/a0v_current_preview_http.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json` 在重启前后均退出0，`CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`，`codeVersion=version=a0v_135`，安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813` approved，四个 pinned 发布版本、binding0。仅预览签名根，不等于 Growth1.13 当前正式信任根。 |
| 顺序重启 | `launchctl bootout gui/501/com.aos.a0v-web-8434` 与 `...api-daily0900` 各退出0，8080/8434/18181 无监听；`docker --context colima-aos-extension restart aos-a0v-recovery-pg` 退出0，短暂 `pg_isready` 未就绪后复核接受连接、库135，PG StartedAt `2026-10-02T07:58:29.478314422Z`；签名预检 GREEN；`launchctl bootstrap` API/Web 各退出0。新 API/Web PID `56531/56532`，18435/8080/8434 监听，18181 无监听。 |
| 健康/八路由 | Python `urlopen` 逐项 `/v1/health`、`/v1/ready`、`/openapi.json`、八 `/workshop/{cockpit,content-campaign,operations,creator-growth,media-studio,analyst,price-governance,customer}` 与 `/aip/skill-publish` 均 HTTP200。组合命令最终 `lsof` 因期望中的18181无监听退出1；HTTP 检查无错误。 |
| 浏览器交互 | 内置浏览器重载 `/aip/skill-publish` 后显示 `org-org/dev-project`、37项仅评测、0正式发布、缺正式发布事件/当前 Logic 版本/模型路由与策略三项、`发布此修订` disabled；点击 `刷新` 后仍如此。八条工作台路由逐页浏览器检查均显示“当前工作台入口不可用”、导航“暂无可见工作台入口”，无加载错误。截图 `w5cb4-daily20261002-latest-e169-{browser,workshop}.png`，SHA256 分别 `8de4dbc8…062746`、`3b66e0df…aaa6b9`。 |
| 当前只读隔离 | 当前库 `read_only=True`：`org-org/dev-project` 唯一安装 approved、ETag3、active_revision NULL；`dev-org/dev-project` 安装0；八类候选 `responsibility_plans/runtime_policies/data_policies/egress_policies/network_policies/quota_policies/budget_policies/budgets` 全0；binding、Host assignment、Host identity、runtime operation 均0。`docker ps -a --filter label=aos.extension.owner` 空。 |

**结论：** `CURRENT_LATEST_PREVIEW_STACK_RESTART_GREEN`。最新代码与当前权威卷已完成 PG→API→Web 全面重启，页面和禁入交互符合现行安全状态。API 仍是 pinned `--serve` 预览路径，不能当正式受限 API；外部 OIDC、独立三身份/Host 凭据、当前正式签名根、Growth1.13 正式发布、八配置、Owner/assignment/binding 与自然首链均未通过。真实库保持只读，Host/worker/Provider未启；未读商城源、未重放旧12 Run、未手工 `run_definition`、未 push。

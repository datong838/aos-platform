# 2026-10-03 11:30 当前最新 m1/权威卷追加完整重启验收

日期：2026-10-03，北京时间约11:30。继当天09:00 完整重启后，开发代码进到 `aos-platform/m1@14a16bb1`，故再次按 PG→API→Web 顺序重启本机预览栈。此为当日质量门，不是正式 Host/首链授权。

| 检查 | 精确证据/退出结果 |
|---|---|
| 代码、权威库与备份 | `git log -1 --oneline`=`14a16bb1`，`git diff --name-only 91d791dd..HEAD -- services/aos-api/alembic/versions` 为空；`docker inspect aos-a0v-recovery-pg` 原卷 `aos-a0v-recovery-pg-data:/var/lib/postgresql/data`，库 `aos_current_preview_20260927`。首次误用 `-U postgres` 返回 role 不存在，按容器已声明的 `POSTGRES_USER=aos_app` 只读回读为 `a0v_135`，exit0。09:00 独立全备 SHA256 `e2c3a4b6881e5b4616b92ce42052227d6a20fa34b4310debcda83c939c9e04a0`，容器 `pg_restore -l` TOC5905，未改/删除备份。 |
| 签名/安装 | `services/aos-api/.venv/bin/python scripts/a0v_current_preview_http.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json`，重启前后 exit0 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`，代码/库135、approved 安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813`、publishedVersions4、runtimeBindings0。 |
| 顺序重启 | `launchctl bootout` Web/API exit0，8080/8434/18181 均无监听；`docker --context colima-aos-extension restart aos-a0v-recovery-pg` exit0，PG StartedAt `2026-10-03T03:30:02.451612953Z`，`pg_isready` 与只读版本回读 exit0；签名预检 GREEN 后原 plist `launchctl bootstrap` API/Web exit0，新 PID API56897/Web56965。 |
| 服务/页面 | 18435/8080/8434 LISTEN、18181 CLOSED；`/v1/health`、`/v1/ready`、八 `/workshop/*` 页面、`/aip/skill-publish` 与 `/aip/agent-catalog` HTTP200。新 API 启动日志 `migrationMode=disabled,runtimeHost=0,workersEnabled=0`、`startup_extension_runtime_host_inactive code=DISABLED`。 |
| 浏览器/业务禁入 | Codex in-app browser CUA 重新加载用户现有 `/aip/skill-publish`，截图和 AX 留本轮工具证据。页面 `org-org/dev-project`，37仅已评测/已发布0；缺正式技能放行事件、当前 Logic 发布版、当前模型路由与运行策略，`发布此修订` disabled；导航“暂无可见工作台入口”。`SET TRANSACTION READ ONLY` 调原候选读者：八类有效配置全0；只读 PG `extension_runtime_binding`、Host assignment/identity 各0。 |

边界：原卷数据不因重启变成新业务事实；本次无全库恢复演练，09:00 独立备份仅 SHA/TOC 校验。API 是本机 `--serve` 预览路径，正式 OIDC、发行/Host 独立身份、Growth1.13 发布、六 Binding、Owner/assignment 和自然首链仍未通过；Host/worker/Provider未启动。没有读商城源、重放旧12 Run、手工 run_definition、删除库/卷/备份或 push。

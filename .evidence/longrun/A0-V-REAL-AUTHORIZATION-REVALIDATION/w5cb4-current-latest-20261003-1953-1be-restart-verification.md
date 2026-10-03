# 2026-10-03 19:53 最新 m1 / 当前权威卷全栈重启回读

依据已批准的 `w5cb4-daily20261003-post-reboot-latest-restart-plan.md`，范围仅为本机禁入预览 PG→API→Web。代码 HEAD `m1@1be7e348a0a23c4cc254d4b65f97547bc5d9d998`，唯一迁移头 `a0v_135`；当前真实库只读，无迁移/切库/Host。

| 门 | 可复核输出 |
|---|---|
| 权威数据与备份 | `docker --context colima-aos-extension inspect aos-a0v-recovery-pg` → `running`，原命名卷 `aos-a0v-recovery-pg-data` 挂在 `/var/lib/postgresql/data`；`psql ... alembic_version` → `aos_current_preview_20260927|a0v_135`，exit0。重启前新 `pg_dump -Fc` 到 `/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-current-backup-20261003-1952-135/current-full.dump`，SHA256 `be40a303c216324b57fc68c61b745f87e7dd2516572a43ad618954f9a71fbbcc`，容器 `pg_restore -l` exit0、5905行；尚未对此份做全库恢复演练。 |
| 签名与安装 | `services/aos-api/.venv/bin/python scripts/a0v_current_preview_http.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json` 重启前后 exit0，`CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`；安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813` approved，publishedVersions4、runtimeBindings0。该签名预检不证明 Growth1.13 正式当前发布。 |
| 顺序重启 | `launchctl bootout` Web/API exit0，8080/8434/18181 全 CLOSED；`docker --context colima-aos-extension restart aos-a0v-recovery-pg` exit0，StartedAt `2026-10-03T11:52:59.484388426Z`，原卷不变；首次 `pg_isready` exit0，数据库版本仍135；原 plist `launchctl bootstrap` API/Web exit0，新 PID 20495/20498，进程启动 19:53:15 CST。API 日志 `migrationMode=disabled,runtimeHost=0,workersEnabled=0` 和 `startup_extension_runtime_host_inactive code=DISABLED`。 |
| 端口与页面 | 18435/8080/8434 LISTEN、18181 无监听。`/v1/health`、`/v1/ready` 200。首次 `/openapi.json` 5秒请求超时，随后重试 0.09秒为200；同一检查的八条 `/workshop/{cockpit,content-campaign,operations,creator-growth,media-studio,analyst,price-governance,customer}` 与 `/aip/{skill-publish,agent-catalog}` 全200，退出0。首次超时保留为冷启动观察，未伪称一次全绿。 |
| 浏览器与真实库只读 | Codex in-app browser CUA 重载 `/aip/skill-publish`：`org-org/dev-project`、37仅已评测、已发布0、正式放行/Logic/模型路由三阻断、`发布此修订` disabled，侧栏无可见电商入口；`/workshop/cockpit` 显示“当前工作台入口不可用”，已在 CUA 输出留截图，返回发布页。当前库 `read_only=True`：八类有效配置均0，Plan head/binding/Host assignment/Host identity/ToolBinding/operation均0；`dev-org/dev-project` Plan head0。 |

结论仅为最新 `m1@1be7e348` 的当前命名卷本机预览栈启动与失败封闭回读；正式受限 API 身份、Growth1.13 当前安装、六 Agent、八配置、Host Owner/binding 与自然首链仍未证。没有读取商城源、删库/卷/备份、重放旧12 Run、手工 run_definition、启动 Host/worker/Provider 或 push。完成后回 s3o-w-ac 原 active rebind。

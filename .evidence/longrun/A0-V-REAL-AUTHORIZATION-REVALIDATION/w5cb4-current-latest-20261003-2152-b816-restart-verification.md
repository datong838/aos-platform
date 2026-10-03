# 2026-10-03 21:52｜Agent 激活修复后的最新栈重启验收

依当日最新栈重启方案，`m1@b81620b5` 与当前命名卷 `aos-a0v-recovery-pg-data` 做 PG→API→Web 有序重启。本波未迁移、未切库，当前库始终只读；Host、worker、Provider 未开启。

| 门 | 实测输出与退出码 |
| --- | --- |
| 代码、库、备份 | `git branch --show-current`=`m1`，HEAD=`b81620b5`；代码/当前 `aos_current_preview_20260927` 均 `a0v_135`；签名安装预检 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`，approved 安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813`、publishedVersions4、runtimeBindings0，退出0。重启前独立全备 `/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-current-backup-20261003-1952-135/current-full.dump` 的 SHA256=`be40a303c216324b57fc68c61b745f87e7dd2516572a43ad618954f9a71fbbcc`，`pg_restore -l` TOC5905、退出0；此份尚未做全库恢复演练。 |
| 有序重启 | Web/API `launchctl bootout`→`docker --context colima-aos-extension restart aos-a0v-recovery-pg`→`pg_isready`→API/Web `launchctl bootstrap` 均退出0。PG StartedAt=`2026-10-03T13:45:17.031089264Z`，保留原卷；新 API/Web PID=`35869/35872`。18435/8080/8434 LISTEN，18181 无监听。API 启动日志明确 Host、cron worker、Logic worker、Provider health maintenance inactive。 |
| 健康与页面 | `/v1/health`、`/v1/ready`、`/openapi.json` 均200；八个 `/workshop/{cockpit,content-campaign,operations,creator-growth,media-studio,analyst,price-governance,customer}` 和 `/aip/{skill-publish,agent-catalog}` 均200；检查命令退出0。 |
| 浏览器禁入 | CUA 重载用户已有 `/aip/skill-publish`；截图工具输出可见 `org-org/dev-project`、37条仅评测、已发布0。AX 回读显示正式技能放行/当前 Logic/模型路由三项缺失、发布按钮 disabled、侧栏“暂无可见工作台入口”；这只证明禁入有效。 |
| 只读业务状态 | `docker ... psql ... -v ON_ERROR_STOP=1 -c 'BEGIN READ ONLY; ... COMMIT'` 返回 `aos_current_preview_20260927|aos_app|a0v_135`；org-org/dev-project AgentInstance6、active0、CapabilityBinding0、Plan head0、runtime binding0、Host assignment0；dev-org/dev-project AgentInstance0、Plan head0；退出0。 |

结论：最新代码在当前权威卷上运行且失败封闭。Agent 激活事务竞态修复已部署于预览 API，但六 Agent 仍 provisioning，当前正式 Binding、Growth1.13 模板来源、受限正式身份和自然经营首链均未就绪。未读取商城源、重放旧 Run、手工运行、写当前库或 push。下一波按 D-waves 继续六 Agent 当前签名模板与精确 Binding 来源；BI 真正不同 UID 和 IdP 身份继续独立实例禁入核验。

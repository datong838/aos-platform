# 2026-10-03 15:32｜BI 发行者事务身份切片后最新栈完整重启

基线 `m1@90dc7e61`、Authority `AOS-001226`。当前权威容器 `aos-a0v-recovery-pg` 绑定原命名卷 `aos-a0v-recovery-pg-data:/var/lib/postgresql/data`、库 `aos_current_preview_20260927`。`git diff --name-only c3d67dbb..HEAD -- services/aos-api/alembic/versions` 为空；代码及 DB 头 `a0v_135`。当天独立全备 `aos-recovery/.aos-current-backup-20261003-post-reboot-135/current-full.dump` SHA256 `e2c3a4b6881e5b4616b92ce42052227d6a20fa34b4310debcda83c939c9e04a0`、pg_restore TOC 实体5890，未恢复或修改备份。

| 门 | 结果 |
|---|---|
| 签名/安装 | `a0v_current_preview_http.py --signed-receipt .../.aos-current-build-pyGkqQ/signing-receipt.json` 重启前后 exit0，`CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`；approved installation `ccdcb0f0-1040-4bc6-aa0c-d045f5689813`，publishedVersions4、runtimeBindings0。 |
| 顺序重启 | Web/API `launchctl bootout` 各 exit0，原 PG 容器 restart exit0，`pg_isready` exit0，签名预检 GREEN 后 API/Web bootstrap 各 exit0。PG StartedAt `2026-10-03T07:32:33Z`，新 API PID705、Web PID744。 |
| 服务/页面 | 18435/8080/8434 LISTEN，18181 无监听；health/ready HTTP200，`/workshop/{cockpit,content-campaign,operations,creator-growth,media-studio,analyst,price-governance,customer}` 八路由均 HTTP200；新 API 日志 `startup_extension_runtime_host_inactive code=DISABLED`。 |
| 浏览器禁入 | Codex in-app browser 重载用户原 `/aip/skill-publish`，AX 与截图见本轮工具证据：`org-org/dev-project`、37条仅评测、发布0、缺正式发布事件/当前 Logic/模型路由策略三项，按钮 disabled，侧栏无可见电商入口。 |
| 当前真库只读 | 原 `RuntimeConfigurationCandidateReader` 经签名预检精确 DSN 回读八类候选全0；PG `BEGIN TRANSACTION READ ONLY` 回读 Plan head/runtime binding/Host assignment/ToolBinding 为 `0|0|0|0`。 |

代码已加载，页面和配置仍失败关闭。BI Plan 独立 issuer 的下一安装锁门仅在一次性 PG 测过；当前真库未获专用 issuer/ACL，也未执行 BI prepare、ToolBinding upsert 或业务首链。Host/worker/Provider保持关闭；未读商城源、重放旧12Run、手工 run_definition、触碰230 L0 或 push。HTTP200 不计经营闭环通过。

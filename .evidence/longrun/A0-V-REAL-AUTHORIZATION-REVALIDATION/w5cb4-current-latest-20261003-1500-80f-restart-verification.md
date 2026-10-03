# 2026-10-03 15:00｜ToolBinding 来源门后最新 m1/原卷完整重启

基线 `m1@80f17122`，Authority `AOS-001224`，上一栈运行代码 `3d43567a`。当前命名卷 `aos-a0v-recovery-pg-data:/var/lib/postgresql/data`、容器 `aos-a0v-recovery-pg`、库 `aos_current_preview_20260927`。`git diff --name-only 513331ba..HEAD -- services/aos-api/alembic/versions` 为空；代码及 DB 均 `a0v_135`。独立全备 `/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-current-backup-20261003-post-reboot-135/current-full.dump` SHA256 `e2c3a4b6881e5b4616b92ce42052227d6a20fa34b4310debcda83c939c9e04a0`，`pg_restore -l` TOC 实体5890。未恢复、删除或修改备份及当前真实数据。

| 门 | 本次结果 |
|---|---|
| 签名/安装预检 | `scripts/a0v_current_preview_http.py --signed-receipt .../.aos-current-build-pyGkqQ/signing-receipt.json` 重启前后 exit0，`CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`，approved installation `ccdcb0f0-1040-4bc6-aa0c-d045f5689813`，publishedVersions4、runtimeBindings0。 |
| 顺序重启 | Web/API `launchctl bootout` 各 exit0；`docker --context colima-aos-extension restart aos-a0v-recovery-pg` exit0；`pg_isready` exit0；原签名预检 GREEN 后 API/Web `launchctl bootstrap` 各 exit0。PG StartedAt `2026-10-03T06:59:01Z`，API PID97308、Web PID97330，原命名卷保持不变。 |
| 健康与页面 | 18435/8080/8434 LISTEN，18181 不监听；`/v1/health`、`/v1/ready` HTTP200；`/workshop/{cockpit,content-campaign,operations,creator-growth,media-studio,analyst,price-governance,customer}` 八路由各HTTP200。新 API 日志 `startup_extension_runtime_host_inactive code=DISABLED`；Host/worker/Provider 未启。 |
| 浏览器实际禁入 | Codex in-app browser 重载用户已有 `/aip/skill-publish`，AX 与截图保存在本轮工具证据。`org-org/dev-project`，37条仅评测、已发布0，正式发布决定/事件、当前 Logic 发布版、当前模型路由与策略三阻断；`发布此修订` disabled，侧栏“暂无可见工作台入口”。 |
| 当前真库只读 | 原 `RuntimeConfigurationCandidateReader` 用签名预检解析的当前 DSN 查询，八类有效候选全0；PG `BEGIN TRANSACTION READ ONLY` 回读 Plan head/runtime binding/Host assignment/ToolBinding 为 `0|0|0|0`，库迁移 `a0v_135`。首次用 `postgres` 角色读版本 exit2（库无该角色），改为容器正式 `POSTGRES_USER=aos_app` exit0；无数据写。 |

本轮加载的是已提交代码，但 HTTP200/签名预检/页面禁入不证明正式 Tool 发行、当前 Growth1.13 发布、六绑定、八配置或经营首链。原 Store 的活跃 Agent 来源门由隔离 PG 18 passed/1 已知 Receipt xfailed 证明；当前无正式 Tool issuer/Receipt，不向真库发 active upsert。没有读商城源、重发旧12Run、手工 run_definition、触碰230 L0 或 push。下一波 s3o-w-n 继续独立发行身份/Receipt，真库迁移另波。

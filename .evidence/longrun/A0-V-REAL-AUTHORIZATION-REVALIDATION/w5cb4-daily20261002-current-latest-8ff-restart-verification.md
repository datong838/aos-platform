# 2026-10-02 最新 m1@8ff64bbf 权威卷完整重启复验

本次复验发生在 `23097ad7` 生成 Host 读者接线与 `8ff64bbf` 浏览器补证后。范围是本机禁入预览栈，不能代替正式 OIDC、Host 身份、配置或经营首链验收。

| 门 | 可复核命令与实测 |
| --- | --- |
| 代码、签名与版本 | `git rev-parse --short HEAD` → `8ff64bbf`；`services/aos-api/.venv/bin/python scripts/a0v_current_preview_http.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json` 在 PG 重启后退出0，`CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`、`codeVersion/version=a0v_135`、安装 `approved`、已发布版本4、运行绑定0。 |
| 数据卷与独立备份 | `docker --context colima-aos-extension inspect aos-a0v-recovery-pg` → `aos-a0v-recovery-pg-data:/var/lib/postgresql/data`；PG `StartedAt=2026-10-02T05:26:00.647782059Z`；库 `aos_current_preview_20260927` 的 `public.alembic_version=a0v_135`。独立备份 `aos-recovery/.aos-current-backup-20261002-cutover135/current.dump` SHA256=`8862e763347caae6c9f9ce1e15aac3e906e6770aa3c53a95bda33678863d8188`，完整恢复演练见当日118→135记录。 |
| 顺序重启与禁入 | `launchctl bootout` Web/API 各退出0；8080/8434/18181 均无监听；`docker --context colima-aos-extension restart aos-a0v-recovery-pg` 退出0，`pg_isready` 成功；签名预检 GREEN；`launchctl bootstrap` API/Web 各退出0。新 API/Web PID `44934/45000`；18435/8080/8434 监听，18181 无监听。 |
| HTTP 与浏览器 | `/v1/health`、`/v1/ready`、`/openapi.json`、八个 `/workshop/{cockpit,content-campaign,operations,creator-growth,media-studio,analyst,price-governance,customer}`、`/aip/skill-publish` 均 HTTP200。首次 OpenAPI 5 秒超时，再试立即200，响应 5,340,043 字节。浏览器 AIP 发布页 37 项仅已评测、0 发布、三来源阻断、按钮 disabled，电商导航无可见入口。 |

当前真实库只读；未开启 Host/worker/Provider、未读商城源、未重放旧12 Run、未手工 Run、未 push。HTTP200 与禁入证明系统安全可访问，不能证明当前实例可正式安装并自然完成首链。

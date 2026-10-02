# 2026-10-02 最新 m1@f5b92473 权威卷完整重启复验

范围仅本机禁入预览栈；当前正式受限 API/Host 身份、八配置和自然首链仍未通过。此前当日完整重启记录见 `w5cb4-daily20261002-current-latest-df5-restart-verification.md`；本次为后续代码提交后的再次完整重启。

| 门 | 实测输出 |
| --- | --- |
| 最新代码与迁移 | `git rev-parse --short HEAD=f5b92473`；签名 `scripts/a0v_current_preview_http.py --signed-receipt .../signing-receipt.json` 在停机前、PG 重启后均回 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`，`codeVersion/version=a0v_135`，`database=aos_current_preview_20260927`、安装 approved、published4、runtimeBindings0。PG 内只读 `public.alembic_version=a0v_135`。 |
| 卷与备份 | `docker --context colima-aos-extension inspect aos-a0v-recovery-pg` 的数据卷仍 `aos-a0v-recovery-pg-data:/var/lib/postgresql/data`；独立备份 `aos-recovery/.aos-current-backup-20261002-cutover135/current.dump` SHA256=`8862e763347caae6c9f9ce1e15aac3e906e6770aa3c53a95bda33678863d8188`，全库独立恢复演练见当日118→135记录。 |
| 零执行重启 | `launchctl bootout` Web/API；复查8080/8434/18181无监听、库其他客户端0；`docker ... restart aos-a0v-recovery-pg` 退出0，PG `StartedAt=2026-10-02T04:53:57Z`，`pg_isready` 接受连接；原签名预检重读 GREEN；`launchctl bootstrap` API/Web 各退出0，新 PID 41892/41895。API日志 `startup_extension_runtime_host_inactive code=DISABLED`，cron/logic automation worker disabled。 |
| HTTP与页面 | 18435/8080/8434 LISTEN、18181无监听；`/v1/health`、`/v1/ready`、`/openapi.json` 与八 `/workshop/{cockpit,content-campaign,operations,creator-growth,media-studio,analyst,price-governance,customer}` 及 `/aip/skill-publish` 均 HTTP200。Codex 浏览器重新加载后37项仅已评测、0发布、三来源阻断、发布按钮 disabled，无可见电商工作台入口。 |

最初 `pg_isready` 在容器刚重启后短暂返回 no response（退出2），随后有界重试通过；shell 里 `curl` 不在 PATH，使用 `/usr/bin/curl` 完成全项 HTTP 验证。没有把端口200当作正式业务 GREEN。未写真实库、未开启 Host/worker/Provider、未读商城源、未重放旧12 Run、未手工 Run、未 push。

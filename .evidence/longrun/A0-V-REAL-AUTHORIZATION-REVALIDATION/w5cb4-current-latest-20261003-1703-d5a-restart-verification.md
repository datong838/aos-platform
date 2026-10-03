# 2026-10-03 17:03 CST｜s3o-w-r 后最新栈重启验收

- 代码 `m1@d5a22fb7`、代码/当前库 migration `a0v_135`；独立备份 `/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-current-backup-20261003-post-reboot-135/current-full.dump` SHA256 `e2c3a4b6881e5b4616b92ce42052227d6a20fa34b4310debcda83c939c9e04a0`，此前 `pg_restore -l` TOC 5890，未声称全库恢复演练。
- 停 API/Web，重启原 PG 容器 `aos-a0v-recovery-pg`；StartedAt `2026-10-03T09:03:10Z`，原卷 `aos-a0v-recovery-pg-data:/var/lib/postgresql/data`，`pg_isready` accepting。最新签名预检 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`，数据库 `aos_current_preview_20260927`、安装 approved、发布版本4、runtimeBindings0。
- 再启 API/Web PID 7613/7617；8080 `/v1/health`、`/v1/ready` 均200，8434 `/aip/skill-publish` 及八个 `/workshop/{overview,growth,customer,merchandise,operations,finance,fulfillment,agent}` 路由均200；18181 无监听。
- IAB 页面 org-org/dev-project，37仅已评测、已发布0、三项正式发布阻断、发布按钮 disabled、电商工作台无可见入口；只读 PG 八类有效配置全0、Host assignment0、ToolBinding0、runtime binding0、BI Plan0。Host/worker/Provider未启，真实库未迁移或写入。HTTP/页面可用仍不计首链。

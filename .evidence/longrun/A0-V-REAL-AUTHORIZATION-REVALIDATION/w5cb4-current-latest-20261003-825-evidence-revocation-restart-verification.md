# 2026-10-03 s3o-w-al 最新代码原卷重启验收

- 代码 `aos-platform/m1@825066cf`，代码/权威库 migration 均 `a0v_135`。当前库 `aos_current_preview_20260927`，容器数据挂载仍为 `aos-a0v-recovery-pg-data:/var/lib/postgresql/data`；PG StartedAt `2026-10-03T15:51:27.269504665Z`。独立全备 `/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-current-backup-20261003-1952-135/current-full.dump` SHA256 `be40a303c216324b57fc68c61b745f87e7dd2516572a43ad618954f9a71fbbcc` 回读一致；该份未做全库恢复演练。
- 签名安装原 preflight 重启前后退出0 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`：安装 approved、publishedVersions4、runtimeBindings0。代码头135不高于库135，无迁移。
- 现场 API 服务标签实际为 `com.aos.a0v-api-daily0900`。Web/API `launchctl bootout` 各退出0，8080/8434/18181 均关闭；原 PG `docker restart` 退出0、`pg_isready` 退出0、只读数据库/版本回读退出0；API/Web 原 plist `launchctl bootstrap` 各退出0，新 PID45561/45578，进程从仓库脚本/ Vite 原路径启动。
- Python HTTP 回读 `/v1/health`、`/v1/ready`、`/openapi.json`，八 `/workshop/{cockpit,content-campaign,operations,creator-growth,media-studio,analyst,price-governance,customer}` 与 `/aip/skill-publish` 全 HTTP200，退出0。端口单独断言 18435/8080/8434 LISTEN、18181 CLOSED，退出0；前次联合 `lsof` 因未监听的18181 返回退出1，非服务故障。
- CUA 用户现有浏览器 tab 重载 `/aip/skill-publish`：`org-org/dev-project`；37 条仅已评测、已发布0；正式放行/当前 Logic/可用 Route+Policy 三阻断，`发布此修订` disabled，导航电商工作台无可见入口。截图 `w5cb4-e17-s3owal-browser-20261003.png`。
- 当前库 `BEGIN READ ONLY`：正租户 Provider/Route/CapabilityBinding 0、dev-org 撤销行0；正式受限 readiness reader role 当前为0。本波只在代码和可销毁 PG 完成撤销门，未创建当前身份/ACL/配置或业务操作；Host/worker/Provider/18181继续禁入。首链 pending。

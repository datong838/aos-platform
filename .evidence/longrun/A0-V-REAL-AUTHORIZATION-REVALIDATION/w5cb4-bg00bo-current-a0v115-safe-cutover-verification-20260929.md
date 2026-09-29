# W5CB4 BG-00bo｜当前权威卷 a0v115 可恢复迁移与最新栈回读

方案：`w5cb4-bg00bo-current-a0v115-safe-cutover-plan-20260929.md`。代码 m1 `2e00e7ac`（精确 schema 预检头），真实库只做本波114→115迁移；无商城源读取、旧12 Run/手工 run_definition、Host/worker/Provider。

| 门 | 可复核命令/输出与退出码 |
|---|---|
| 进入身份 | `docker --context colima-aos-extension inspect aos-a0v-recovery-pg --format ...` 退出0，挂载 `aos-a0v-recovery-pg-data:/var/lib/postgresql/data`；当前库 `aos_current_preview_20260927@a0v_114`，签名预检 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`、approved1/published4/binding0、签名根当前。初次只读计数误写不存在的 `bundle_runtime_binding` 退出1，改为 `extension_runtime_binding` 后退出0：安装1、制品版本4、binding0。|
| 方案/RED | `test_a0v_current_preview_http.py` 新断言115：RED 1 failed/2 passed；只改 `scripts/a0v_current_preview_http.py::EXPECTED_SCHEMA_HEAD`，GREEN 3 passed，退出0。|
| 零执行窗口 | Web `launchctl bootout gui/501 ...com.aos.a0v-web-8434.plist`、旧 API PID71497 `SIGINT` 退出0；8080/8434/18181 `lsof` 均无监听（各退出1），当前库 `pg_stat_activity` 其他会话0、源版本114。Host/worker/Provider 未开。|
| 独立备份 | 停机后 `pg_dump -Fc` 到 `/Users/ddt/work/projects/ai_agent/.aos-current-backup-20260929-bg00bo-gf9Isg/aos_current_preview_20260927_a0v114.dump`，退出0；3,950,274 bytes、0600、SHA256 `e4bd14927ec39f77ff2d50942d19f60097c07a31ad0b3336333c7dc34f028d58`，`pg_restore -l` 退出0/TOC 5607。保留 BG00bn 另份备份，不覆盖。|
| 第二全库克隆 | 新 test-only `aos_bg00bo_cutover_20260929`，`pg_restore --no-owner --single-transaction --exit-on-error` 退出0；源/克隆五张控制表 count+MD5 精确一致（bundle_installation1、revision3、asset_bundle4、version4、binding0），克隆114。程序化 Alembic 仅克隆114→115退出0；五固定 ID runtime INSERT 均42501、普通 ID INSERT 成功并 rollback，测试命令退出0。克隆保留。|
| 当前迁移 | 再核 8080/8434/18181 无监听、其他会话0、卷身份和源114后，对精确当前库 Alembic114→115退出0；ActionType行0、保留触发器1。五张控制表 count+MD5 与第二克隆迁移后仍完全一致；无业务行写入。|
| 最新栈 | `docker restart aos-a0v-recovery-pg` 退出0，原命名卷挂载与当前115/安装1/制品4/binding0 回读退出0；签名预检 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN` 退出0。最新 m1 API session90597 启动日志 `migrationMode=disabled`、runtime Host disabled、worker disabled、Provider health inactive；Web LaunchAgent bootstrap 退出0。18435/8080/8434 监听，18181 无监听。API `/v1/health`、`/v1/ready`、`/openapi.json` 均200；Web 八 `/workshop/*` 路由及 `/aip/skill-publish`、`/aip/agent-catalog` 均200。首次路由循环错误使用 zsh 保留变量 `path` 导致 `curl` 找不到（退出127），换独立 `aos_route` 重跑退出0且全部200。|
| 租户/禁入 | 当前库 `BEGIN READ ONLY` 查 `org-org/dev-project` 安装1、`dev-org/dev-project` 安装0，operation/binding/Host assignment各0，`a0v_115`；退出0。五类新 active Store 门未解除。|

复审：方案中的备份、第二克隆、零窗口、当前迁移与最新栈顺序均满足；无删除库/卷/备份，test-only 两克隆保留。`a0v_115` 只增加系统 ID 数据库保留门；正式 ActionType/Producer/审批消费和配置仍不存在。browser-pilot 在当前工具环境不可用，故无截图/交互验收；HTTP 200 不证明首条经营链或八工作台业务功能。下一波 BG-00bp 回到 E17 正式 NetworkPolicy Producer/预览与审批链设计，优先使产品能从当前身份产生精确审批候选；Runtime Host/worker/Provider 继续关闭。

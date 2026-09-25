# W5c8s｜真实 profile 重启前只读审计

## 已证

- `colima list`：`aos-extension` 停止、`aos-a0v-test-only` 运行；本波未启动真实 profile。18181 无监听；8080 有 `com.aos.a0v-api-8080` 的 uvicorn 进程，launchd 配置 `RunAtLoad=true`、`KeepAlive=true`。
- `launchctl print gui/501/com.aos.a0v-api-8080` 只读回显：`AOS_EXTENSION_RUNTIME_HOST_ENABLED=1`、`AOS_SNAPSHOT_GROUP_WORKER_ENABLED=true`、`AOS_SNAPSHOT_GROUP_WORKER_TOPOLOGY=independent`。plist 未设置 `AOS_QYH_CRON_ENABLED`、`AOS_DB_MIGRATION_MODE`；代码 `main.py` 的 Cron 默认 `true`，`migrations.py` 的迁移模式在显式值缺失时为 `LEGACY_BOOTSTRAP`（另有 legacy env 兼容，活动值未核实）。因此不能把当前 8080 当作纯 HTTP/零 Host/零 worker。
- `a0v_096→097→098` 是仓库顺序；隔离 PG head 安装通过，但真实数据库版本/权限/容器 restart policy 仍未知。`colima.yaml` 只见 Colima `autoActivate=false`、`provision=null`，不能据此证明 VM 内 Docker 容器不自动重启。
- 全仓 `pipeline_snapshot_group_witness_backfill_a0v_098` 调用点只在 migration 和测试；未接应用。原 12 Run/Receipt 的当前状态无新鲜真实 DB 读回。

## 停止结论及安全续路

**STOP_PROFILE_START**：若现在启动 `aos-extension`，已运行/可由 launchd 保活的 8080 可能在数据库恢复时拉起 Host、独立 snapshot worker 与默认 Cron，进而改变真实 attempt。没有先停用并读回 8080 的全套执行开关、证明真实容器 auto-start 策略及 DB-only 启动路径，不允许 `colima start`。不能为求读回而先制造执行风险。

后继先方案化受控停止/隔离 8080（含 launchd KeepAlive）、零 Cron/worker/Host 的纯 HTTP 读回、真实 profile 容器重启策略证据、明确禁用迁移；全部证据齐全才另波考虑 DB-only 启动。此审计不授权真实 migration、历史扫描、回填或 ACK。

## 凭据暴露风险

启动 plist 包含明文数据库口令。一次本波只读终端筛选误把该字段打印到工具输出；未在证据/提交中保存口令，也不在此复述。需在可控停机/读回门下安排凭据轮换并检查日志/终端可见范围；本波不直接轮换以免使当前 8080/真实恢复状态变得更不确定。

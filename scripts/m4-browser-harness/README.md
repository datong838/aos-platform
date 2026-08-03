# M4-4 浏览器隔离环境

该 harness 只用于 M4-4 证明波。它启动独立 PostgreSQL 16、真实 `aos-api`、透明 JWT 代理和真实 Vite Web；不修改生产模块，不增加生产端点，不向 Web 注入 fixture，也不 Mock `fetch` 或 DOM。

## 启动与停止

```bash
bash scripts/m4-browser-harness/start.sh
bash scripts/m4-browser-harness/health-check.sh
bash scripts/m4-browser-harness/stop.sh
```

Codex/CI 等会在命令返回时强制回收子进程的执行器，可在第一终端使用 `AOS_M4_FOREGROUND=1 bash scripts/m4-browser-harness/start.sh` 保持监督进程，再从第二终端运行健康检查或浏览器验证；`Ctrl-C` 会执行同一精确清理。

默认地址：

- Web：`http://127.0.0.1:1420/apollo/cases`
- API 健康：`http://127.0.0.1:18080/v1/health`
- JWT 代理 API：`http://127.0.0.1:18081/v1/integration-cases?scope=current`
- PostgreSQL：仅绑定 `127.0.0.1:55432`，容器名 `aos-m4-browser-pg`

测试身份是 `operator:m4-browser`，租户为 `dev-org/dev-project`，角色为 reader/maker/projector，markings 为 `public/restricted`。JWT 由真实 `/v1/auth/token` 颁发，仅保存在权限为 0600 的临时状态目录；浏览器请求经透明代理替换 Web 的开发 Bearer，不在日志或页面暴露 token。

## 确定性场景

环境包含两个 current Case 和一个独立 reference Case：

- `M4 稳定连接案例`：服务端 `connection_verified`，可验证详情、8 门和 timeline。
- `M4 可过期连接案例`：连接 Evidence 默认在启动后 120 秒到期；到期后的列表或详情读取会触发生产 expiry projector，降级为 `planned` 并追加 Stage Event。
- `M4 脱敏参考案例`：无 owner/Installation/Overlay/Lock/current stats。

精确 Case ID 和 `expiresAt` 写入临时 `seed.json`。可通过 `AOS_M4_EXPIRY_SECONDS` 调整到期窗口；端口和状态目录分别可用 `AOS_M4_PG_PORT`、`AOS_M4_API_PORT`、`AOS_M4_PROXY_PORT`、`AOS_M4_WEB_PORT`、`AOS_M4_STATE_DIR` 覆盖。

## 真实性边界

数据库结构来自仓库内六个生产资产 migration；Case 创建通过生产 `IntegrationCaseService`，Evidence 通过生产 `TrustedEvidenceWriter`，reference 通过生产 Store 的独立脱敏写入。API 进程运行生产 `aos_api.main:app` 与 Router wiring。由于当前仓库的全量 managed migration 明确尚未就绪并 fail-closed，harness 在预建隔离库后以 `AOS_DB_MIGRATION_MODE=disabled` 启动 API，避免把不完整 managed inventory 伪装为 GREEN。

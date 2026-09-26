# W5CB4 P2g21：Mac/Colima 当前实例入口只读定位

日期：2026-09-27。方案先行 `m1@42419ee2`。只读检查；无服务启动、DB SQL 业务读取、源库读取或环境值输出。

## 新鲜现场

- `colima status` 未指定 profile 报 default 未运行；`colima list` 显示 default Stopped、`aos-a0v-test-only` Running、`aos-extension` Running。不能以 default 状态断言真实 profile 停止。
- 当前 Docker context 为 `colima-aos-a0v-test-only`，仅 `aos-a0v-test-pg`（postgres:16，127.0.0.1:5433→5432）Up；`colima-aos-extension` 中仅 `aos-a0v-recovery-pg`（postgres:16，127.0.0.1:18435→5432）Up。恢复容器 `restart=no`、state=running、bridge 网络，`pg_isready` accepting。18435 的本机监听是 SSH 转发；未检查 DB 业务行。
- 8080/18181/5173 均无监听，`com.aos.a0v-api-8080` 当前 launchd 列表未见。没有识别到现行 AOS API/Host/worker 进程。既有 W5c8z 证据把 18435 标作唯一恢复 PG 容器；当前只确认入口/运行态，不据此推定库内安装、迁移或原 Run 状态。
- P2g19 从 `.env`/默认 DSN 打开的 5433 `aos_meta` 是测试专用 profile 的空开发库；它与 18435 恢复 PG 是两个不同入口。必须纠正“默认库空”与“恢复库当前权威缺失”的混淆。无可信当前 API/Host 授权可用，不能为浏览器验收或 Worker 绿而启动 8080/启新 flag。

## 门禁与下一波

- `VERIFIED`：本机两个 Colima profile 的容器/端口归属、恢复 PG 容器运行/无自动 restart、API 端口离线。
- `NOT_VERIFIED`：18435 内具体 DB/签名 Bundle 安装/租户权限/Host/来源/预算/真人审批/原反馈自然状态；未做业务 SQL。
- 下一波 P2g22 只读对 18435 恢复 PG 做**精确 DB 身份、迁移、签名安装和 Host 状态**读回，先复习 W5c9 受控只读脚本/权限并限制到元数据表；不得读商城源或旧 Run payload。若读回失败/版本漂移，冻结，不自动启动 API、Host、worker，不手工 run_definition。此入口确认后才可单独规划受控 HTTP/浏览器复验。

# W5c7v Worker/Owner fence 覆盖矩阵 verification

方案 `f7f8bc08` 先行；实施仅新增 `w5c7v-worker-owner-fence-coverage-audit-20260925.md`，无生产代码、真实 DB/Host/定义变化。矩阵逐项对照 API 独立 Snapshot worker、A0-V Runtime Host 三业务 worker、PipelineControlServices、AutomationOccurrenceStore、DataRequirementOutboxStore 与既有 Schedule/Recovery opt-in；`host_ready` 和 delivery lease 都不是同事务 Host fence。未证跨事务及外部效果保持 no-effect，下一波仅选择单一 Owner 路径。

测试第一次把 Host lease PG 合同与 worker suite 混在同一 pytest 会话：37 passed、7 setup `KeyError: AOS_DATABASE_URL`。隔离 PG test 依赖 session 临时 DSN，组合顺序改变了环境；独立会话重跑 Host lease **7 passed**，其余 37 已通过。该顺序债尚未修复，不能报告为联合 44 项一轮 GREEN。近期 A0-V 累计回归单独 **237 passed**、7 warnings/20.91 秒；旧长例未重跑。临时 `aos_test_%` 库 0，测试 PostgreSQL 停回原态；`git diff --check` 通过。

浏览器 2026/9/25 18:36:08 CST 只读核对 A0-V Canonical rev4「已停用」且「数据组已停用」，待同步写操作 1 未冲刷；临时页面/Vite 已关闭。真实 closure 只读门仍 `automaticAction=false`、`closureAuthorized=false`、`topologyComplete=false`、12 原 Run running、stalled Receipt 0，缺全机拓扑、Fresh Owner 同事务门、独立 closure 方案/key；严格 24h 资格晚于 2026-09-25 20:00:04.800482 UTC，也不自动授权。

复审：不改代码是安全边界选择，不把局部 opt-in 误外推；生产 `main.py` 和 A0-V Host 的 worker fence 仍未覆盖。下一波 W5c7w 先方案，对 `PipelineControlServices` 的 selection/control/bind 三个单事务 Owner 写入口做 default-off fence 设计及隔离测试；三业务 worker 的跨事务路径另列。旧 attempt 不重发、不手工 run_definition；商城源行不读、230 L0 挂起、dev-org 零 canary、m1 不 push。

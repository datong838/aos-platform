# W5c6m Host 节点全集来源审计验证（2026-09-25）

## 第 1/9～4/9 步：方案、清单与最小合同

- 上位 W5c6j–l 和正式 closure 门复习后，方案先提交 `49b826aa`。
- 仅新增静态无效应合同 `services/aos-api/tests/extension_runtime/test_a0v_w5c6m_host_fleet_source_audit.py`，提交 `de2565f3`；未改生产、部署、DB、Host。
- 审阅 dev launchd plist 只描述本机一个 launcher；spoke-full Helm 是另一服务的可变副本模板。已审阅仓库/部署来源没有可证明 A0-V Runtime Host 跨机器节点全集的权威来源；本机/受管目录/数据库会话零计数不推出全集。

## 第 5/9～7/9 步：测试、只读验收与复审

- 专项静态合同 3 passed；W5c5k–z/W5c6a–m 累计回归 80 passed。隔离测试 PG 已停止。
- 浏览器只读 `127.0.0.1:5174/data/schedules` 的整组采集列表显示 A0-V Canonical 首装 `已配置 · 已停用 · 版本 4`。页面存在 1 个待同步写操作，未冲刷；浏览器仅为局部 UI 证据，不代替 DB/Owner 门。
- 真实合成门只读返回 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、`automaticAction=false`、`closureAuthorized=false`、`runningOriginalRuns=12`、`stalledClosureReceipts=0`；严格到线时间 `2026-09-25T20:00:04.800482+00:00`。这不授权提前或到线后自动执行。
- 核对方案一致：没有把本机零计数/配置副本数宣称为全机拓扑，未触发 Store/closure side effect。`FULL_MACHINE_HOST_TOPOLOGY`、`FRESH_SINGLE_TRANSACTION_OWNER_GATE`、独立正式计划/唯一 key 仍缺；不因更多静态合同而变绿。

## 第 8/9～9/9 步：上下文与下一波

- 本文件落盘并提交后 CAS 更新 docs/AOS 项目开发上下文、Prime 独立受管记忆，读回状态与校验；对应提交记录见 docs context54。
- 下一波 W5c6n：处理可独立完成的 `AOS_DATABASE_URL` 组合测试 fixture 顺序与旧 skip 可验证性债；先方案再改代码，A0-V 真实门保持 no-effect。

m1 单写、不 push；旧 attempt 不重发；不读商城源行；230 L0 挂起；dev-org 仅零 canary。

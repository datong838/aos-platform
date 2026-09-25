# W5c8c 原 attempt 双 Receipt 只读寻址与恢复门审计计划

## 上位与范围

承接 231、A0-V fail-closed、W5c8a/b `5dd544cd`/`c65bc58a`。当前自动入口已在代码/隔离 PG 冻结歧义，但真实库未迁移、服务未重启；W5c8b 只证明**已提交 ACK**可由独立 SELECT 确认。本波仅审计 `unknown` 与过期 `claimed` 两类未 ACK 原 attempt：能否从持久元数据只读、唯一地找到 RUNNING AnalysisRuntimeReceipt 与 fulfilled DataFulfillmentReceipt，以及它们是否绑定原 Requirement/Run/租户/源组。不得调用 coordinator/source，不改生产代码或真实 DB；若证明需要新 SQL/恢复 authority，后继另立方案。

## 文件级清单

- 读 `aos_api/ecommerce_analysis_snapshot_coordinator.py::_replay_committed`、`ecommerce_analysis_data_requirement_route.py`、`ecommerce_growth_runtime_adapters.py::_HostAnalysisReceiptStore`、`data_requirement_outbox_store.py`；SQL `alembic/versions/a0v_050_data_requirement_outbox_completion.py`、`biw2_004_data_requirement_outbox_delivery.py`。
- 读 W5c8b 隔离 PG 证据与 `test_analysis_snapshot_coordinator_pg.py`，对照 `claim/unknown/acked` 的查找和唯一性。
- 仅新增本目录 audit/verification；发现可独立修复的问题，先列精确文件/失败动作，不在本波扩大为生产改动。

## 九步

1. 复习 m1/authority/真实 gate 与上位方案，确认 PG/真实服务边界。
2. 本方案先提交，固定原 attempt、双 Receipt、租户及不重发判定。
3. 画出 `acked`、持久 `unknown`、过期 `claimed` 三态的只读寻址与允许/禁止迁移矩阵；标明数据缺失、多候选、提交不明的停止条件。
4. 跑现有 route/Outbox/Receipt 专项中不触源的确定性部分，记录未覆盖项。
5. 跑近期短累计；不重跑 W5c8b 已证明的三条长例。
6. 内置浏览器只读 rev4/停用，队列不冲刷。
7. 代码/SQL/方案一致性复审；若缺少唯一只读证据或过期 claimed 不能合法转 unknown，维持冻结，不设计隐式重领。
8. audit/verification 落盘提交、AOS CAS/Prime 回读，明确不是恢复授权。
9. 自动进入 W5c8d：先方案实现最小只读 resolver 与隔离 PG 负例；如需状态写入另设独立 authority，不混入只读波。

m1 单写不 push；商城源行不读；旧 A0-V attempt 不重发、不手工 `run_definition`；真实 closure 缺全机拓扑、Fresh Owner、独立 plan/key；230 L0 挂起、dev-org 仅隔离 canary。

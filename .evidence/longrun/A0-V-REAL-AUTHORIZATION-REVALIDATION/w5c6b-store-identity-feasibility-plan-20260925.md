# W5c6b Store 物理 DB/角色与事务围栏可行性只读方案（2026-09-25）

上位 W5c6a：原 Store 独立 SQLAlchemy `engine.begin()`；controlled `_authoritative_store` 由 `runtime_worker_dsn()` 建 engine，而原 metadata 走 `runtime_worker_connection()`，但代码同 DSN 不等于实时物理连接证明。Store `_apply_transaction_scope` 在自有事务 `SET LOCAL ROLE aos_runtime` 并设租户 GUC。group Schedule/Recovery 根尚未向 Completion 传 lease；真实 DB 仍 `a0v_092`。

## 文件级九步

1. 复习 Store 组装、原事务作用域、runtime DSN/role、`a0v_094` 权限与 W5c6a effect 边界。
2. 本方案先提交。新增只读 `scripts/a0v_w5c6b_store_identity_feasibility.py` 与纯函数合同测试 `services/aos-api/tests/extension_runtime/test_a0v_w5c6b_store_identity_feasibility.py`，verification；不改生产 Store 或真实 DB。
3. 审计用同一现有 runtime DSN 分别开原 metadata 与 Store SQLAlchemy 连接，只查询不可敏感连接指纹（database、server port、database OID、postmaster start、当前 role、`a0v_094` 函数是否存在）。绝不打印 DSN、密码、源数据或角色口令；不调用 lease acquire/fence 或 Store apply。
4. 纯函数测试“同库/同 runtime role/函数存在”方可判为候选可行，任何缺口冻结；真实审计只读运行并如实报告。
5. 累计无效应/围栏组回归；读库不改库，隔离 PG 无需启动。
6. 浏览器只读核 A0-V rev4 disabled，不保存/运行/冲刷队列。
7. 只读门禁和方案/代码复审；即便候选可行也不等于 Store 事务已围栏，更不等于全机器排他。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文和 Prime 独立受管记忆并读回。
9. 下一波 W5c6c：依据审计结果，若同库且权限满足，再方案先行隔离 PG 测 Store 自有事务内 guard；否则 receipt-first 替代设计。根 Host flag 默认关。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。

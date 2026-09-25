# W5c6c 隔离 PG Store 自有事务围栏可行性方案（2026-09-25）

上位 W5c6a/b：真实 Store 与 metadata 同一物理库/同 runtime 登录，但真实库 `a0v_094` 缺失，Store effect 不可接线；隔离 PG 已有 `a0v_093/094` 合同。Store `_apply_batch` 使用 SQLAlchemy 自有 `engine.begin()` 并在事务内 `SET LOCAL ROLE aos_runtime`。`OptInHostLease.fence_in_transaction` 目前接受 psycopg 风格 `execute`，须验证同事务 SQLAlchemy 适配，不可在 guard 外另开连接。

## 文件级九步

1. 复习 Store `_apply_batch` 原事务、角色/GUC、W5c6b 真实只读结果与 W5c5k worker fence 原型。
2. 本方案先提交。只新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c6c_isolated_store_transaction_fence_pg.py` 和 verification；不改生产 Store、真实 DB、Host flag。
3. 在隔离 PG 用 runtime DSN 建 SQLAlchemy `engine.begin()`，原 `_apply_transaction_scope` 后用同一 SQLAlchemy transaction 的薄适配器调用 `OptInHostLease.fence_in_transaction`。不能使用第二连接作 worker guard。Store 侧仅 `SELECT`/事务范围测试；隔离 lease fixture 可写自身租约表以模拟过期，不写 Store 行。
4. 覆盖默认无 effect、有效 holder、未 acquire/错 scope/epoch/过期拒绝；验证失败拒绝在测试 body 前。
5. W5c5k–z 与 W5c6a–c 累计；旧 skip/timeout 债如实报告，停隔离 PG。
6. 浏览器只读核 A0-V rev4 disabled，不保存/运行/冲刷队列。
7. 真实门禁仍只读。隔离可行仅是候选实现设计输入，不允许给真实 Store 接线或迁移。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文和 Prime 独立受管记忆并读回。
9. 下一波 W5c6d：方案先行设计 Store 原事务内可选 fence API、精确类型/同 scope/预提交校验及回执 replay 语义；隔离 PG 测后再决定是否实现，真实默认关闭。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。

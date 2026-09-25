# W5c5v Snapshot Completion metadata + Attempt opt-in 围栏核验（2026-09-25）

方案 `6764eb4d` 先行，实现 `bd12ea03`。真实 DB 未迁移 `a0v_093/a0v_094`，Host flag 未启用。

## 九步证据

1. 复习 Completion claim-before-execution、`_finish`/stopped recovery 原 `_transaction`、Attempt 心跳/settle 与下层独立 Store effect 边界。
2. 仅 `pipeline_snapshot_group_completion.py` 加可选精确 `OptInHostLease`，包装本类原 metadata 事务 guard，并传同一 lease 给内部 `RecoverableStoreAttemptOwner`；新增 `test_a0v_w5c5v_completion_metadata_fence_pg.py`，更新 W5c5r 静态结构合同。下层执行器/Store 未改。
3. 默认 None 原样；opt-in 时本类每笔 metadata 事务和内部 Attempt 各笔心跳/settle 独立验证当前 holder。一次通过不覆盖后续事务；未知提交不重发旧 attempt。
4. 隔离 PG 新专项 **2 passed**，连续三笔有效事务、默认、未 acquire/错 scope/epoch/过期拒绝，同一 lease 传递。旧 Completion 无 Store 定向 **2 passed、3 deselected**。首测用未初始化 Owner 替身失败，改成只替换下层执行器后通过。
5. 累计主组 **162 passed**、W5c5k–v 围栏/结构组 **31 passed**、定义合同 **24 passed**，合计 **217 passed**；旧 Completion 定向另 2 passed。初次累计红灯是 W5c5r 静态测试要求“尚未传租约”，按本波方案更新为“同租约已传递”并重跑全组绿。旧 Schedule 完整套件超时、Attempt PG 17 skipped 与 `AOS_DATABASE_URL` 顺序债保留。隔离 PG 已停，`git diff --check` 通过。
6. 5174 浏览器只读见 A0-V “已配置 · 已停用 · 版本 4 · 十二类来源”，`BROWSER_PARTIAL`；未保存、运行、冲刷队列，临时页/Vite 已关闭。
7. 实时门禁 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`，`closureAuthorized=false`、12 原 Run running、stalled Receipt 0。Object/Link/Retirement/Single 下层独立事务与 Store effect 未全链路围栏，不得关闭旧组。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c5w：Object→Single 原 metadata 事务逐层 opt-in 围栏，Store effect 另列；不能宣称全链路排他。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。

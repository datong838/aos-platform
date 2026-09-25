# W5c5u Snapshot Recovery 入口 metadata opt-in 围栏核验（2026-09-25）

方案 `c256d4bc` 先行，实现 `e83e5f58`。真实 DB 未迁移 `a0v_093/a0v_094`，Host flag 未启用。

## 九步证据

1. 复习 Recovery `resume_saved` 的唯一 receipt/current definition/original claim 事务与 Completion 独立下游执行边界。
2. 仅 `pipeline_snapshot_group_recovery_runtime.py` 加可选精确 `OptInHostLease`，入口 `_transaction` 在业务体前 guard；新增 `test_a0v_w5c5u_recovery_root_fence_pg.py`。Completion/Ingress/Store 不改。
3. 默认 None 原样；未 acquire、错 scope/epoch、过期在业务体前 fail closed。入口通过不授权后续 Completion/Store。
4. 隔离 PG 新专项 **2 passed**；旧 Recovery 合同定向 **1 passed**。没有恢复真实 saved group，也没有源读或 Store effect。
5. 累计主组 **162 passed**、W5c5k–u 围栏/结构组 **29 passed**、定义合同 **24 passed**，合计 **215 passed**，另旧 Recovery 定向 1 passed。W5c5t 完整旧 Schedule 三模块套件超时未绿、旧 Attempt PG 17 skipped 与 `AOS_DATABASE_URL` 顺序债保留。隔离 PG 已停，`git diff --check` 通过。
6. 5174 浏览器只读见 A0-V “已配置 · 已停用 · 版本 4 · 十二类来源”，`BROWSER_PARTIAL`；未保存、运行、冲刷队列，临时页/Vite 已关闭。
7. 实时门禁 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`，`closureAuthorized=false`、12 原 Run running、stalled Receipt 0；旧组关闭不授权。真实 Host 不启用，旧 attempt 不重发。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c5v：Completion claim/finish/stopped recovery 各 metadata 事务 opt-in guard；下层独立事务/Store effect 继续分波。

m1 单写不 push；商城源行不读；230 L0 挂起；dev-org 零 canary。

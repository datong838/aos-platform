# W5c5s Snapshot metadata connector 围栏角色探针核验（2026-09-25）

方案 `b62374aa` 先行，隔离角色探针 `abf445aa`；生产执行路径/权限未改。

## 九步证据

1. 复习 Snapshot worker 生产构造的 `runtime_worker_connection`、原 ingress `_transaction`、`apply_asset_transaction_scope` 与 `a0v_094` 的登录成员/当前角色检查。
2. 仅新增 `test_a0v_w5c5s_metadata_fence_role_pg.py` 和本 verification；真实连接/Host/DB 不改。
3. 隔离 PG 复刻无预设 `SET ROLE` 的 runtime 登录成员连接，原 metadata 事务进入后 current_user=`aos_runtime`，session_user 保留原登录，GUC 精确租户；同事务调用 worker fence 有效。
4. 专项 **2 passed**：有效 holder、未 acquire/错 epoch/错租户/过期拒绝；新连接角色复原。不读取商城源或 Store 行，不证明真实角色拓扑。
5. 累计主组 **162 passed**、W5c5k–s 围栏/结构组 **25 passed**、定义合同 **24 passed**，合计 **211 passed**；旧 Attempt PG 17 skipped 与 `AOS_DATABASE_URL` 顺序债保留。隔离 PG 已停，`git diff --check` 通过。
6. 5174 浏览器只读见 A0-V “已配置 · 已停用 · 版本 4 · 十二类来源”，`BROWSER_PARTIAL`；未保存、运行、冲刷队列，临时页/Vite 已关闭。
7. 实时门禁 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`，`closureAuthorized=false`、12 原 Run running、stalled Receipt 0。隔离角色兼容不等于真实 `a0v_093/a0v_094` 已迁移，不覆盖下层独立事务、Store effect 或全机器排他。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c5t：给 Snapshot metadata 根事务最小 opt-in Host lease guard，再逐波覆盖下游独立事务/外部 effect；始终默认关闭。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。

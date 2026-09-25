# W5c5t Snapshot Schedule 入口 metadata opt-in 围栏核验（2026-09-25）

方案 `a95db6f0` 先行，实现 `8bf30d93`。真实 DB 未迁移 `a0v_093/a0v_094`，Host flag 未启用。

## 九步证据

1. 复习 Schedule Runtime definition/claim 与 route 两个入口事务、W5c5s 原形连接角色探针。
2. 仅 `pipeline_snapshot_schedule_runtime.py` 增可选精确 `OptInHostLease`，两笔 `_transaction` 在业务读写前入体 guard；新增 `test_a0v_w5c5t_schedule_root_fence_pg.py`。Recovery/Completion/Ingress/Store 未改。
3. 默认 None 保持旧路径；显式 opt-in 时未 acquire、错 tenant/epoch、过期在业务体前 fail closed。入口事务通过不代表下层独立事务或外部 effect 获权。
4. 隔离 PG 新专项 **2 passed**，有效 holder 连续两笔事务、默认、未 acquire/错 tenant/epoch/过期覆盖；旧 Schedule 定向 **4 passed、3 deselected**。未发真实 Schedule claim。
5. 累计主组 **162 passed**、W5c5k–t 围栏组 **27 passed**、定义合同 **24 passed**，合计 **213 passed**，另旧 Schedule 定向 4 passed。完整旧 Schedule 三模块套件在约 5 分钟有界观察仍无终态、测试进程被 SIGINT 中断，**不计通过**；需分组定位。旧 Attempt PG 17 skipped 与 `AOS_DATABASE_URL` 顺序债保留。隔离 PG 已停，`git diff --check` 通过。
6. 5174 浏览器只读见 A0-V “已配置 · 已停用 · 版本 4 · 十二类来源”，`BROWSER_PARTIAL`；未保存、运行、冲刷队列，临时页/Vite 已关闭。
7. 实时门禁 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`，`closureAuthorized=false`、12 原 Run running、stalled Receipt 0；旧组关闭不授权。真实 Host 不启用，旧 attempt 不重发。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c5u：Recovery Runtime 入口事务 opt-in 围栏，并继续拆分完整旧 Schedule 回归超时；Completion/Ingress/Store 分波。

m1 单写不 push；商城源行不读；230 L0 挂起；dev-org 零 canary。

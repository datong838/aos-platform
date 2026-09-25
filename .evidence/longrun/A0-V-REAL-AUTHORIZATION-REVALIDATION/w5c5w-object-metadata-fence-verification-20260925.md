# W5c5w Snapshot Object metadata opt-in 围栏核验（2026-09-25）

方案 `3b5c9604` 先行，实现 `f35c3f8d`。真实 DB 仍是 `a0v_092`，未迁移 `a0v_093/a0v_094`，Host flag 未启用。

## 九步证据

1. 复习 Object 各笔 `_transaction`、Single ingress metadata 角色、W5c5s 同形 connector 探针、W5c5v Completion 边界；确认 Single 内部独立事务和 Store effect 另有边界。
2. 仅 `pipeline_snapshot_group_object_executor.py` 增加可选精确 `OptInHostLease`，包装 Object 自身 `_transaction` guard；新增 `test_a0v_w5c5w_object_metadata_fence_pg.py`，更新 W5c5r 静态合同。没有修改 Single、Link、Retirement 或 Store。
3. 默认 None 保持原事务；显式 opt-in 时本类每笔 metadata 事务在 body 前独立验证 holder。未 acquire、错 scope、错 epoch、过期均 fail closed。上层未传 lease，不能宣称生产链路已生效。
4. 隔离 PG 新专项与结构合同合计 **5 passed**；覆盖默认、有效 holder 连续三笔、四类拒绝。旧 Object 无 effect 定向 **2 skipped、6 deselected**，没有伪称绿灯。
5. 累计主组 **162 passed**、W5c5k–w 围栏/结构组 **33 passed**、定义合同 **24 passed**，合计 **219 passed**。旧 Schedule 完整套件超时、Attempt PG 17 skipped、`AOS_DATABASE_URL` 跨模块顺序债保留。隔离 PG 已停，`git diff --check` 通过。
6. 5174 浏览器只读见 A0-V “已配置 · 已停用 · 版本 4 · 十二类来源”，`BROWSER_PARTIAL`；未保存、运行或冲刷队列，临时页面/Vite 已关闭。
7. 实时门禁 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`，`closureAuthorized=false`、12 原 Run running、stalled Receipt 0；最晚原 Run started_at 为 `2026-09-24 20:00:04.800482 UTC`，严格 24h 条件尚未到。Object 仅局部能力，Single 内部事务、Store effect 与 Link/Retirement 上层租约传递未完成；不得关闭旧组或重发旧 attempt。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c5x：Single ingress `_transaction/_run_transaction` 原 metadata 事务 opt-in guard；继续单独审查 `finalize_saved_dataset` 的 Store effect。

m1 单写不 push；商城源行不读；230 L0 挂起；dev-org 零 canary。

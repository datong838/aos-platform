# W5c5z Link/Retirement/Completion 顶层 opt-in lease 传递方案（2026-09-25）

上位 W5c5r–y：Object→Single→ingress 的原 metadata 事务可同 holder guard；Completion 自身 metadata 与 Attempt 也已 opt-in，但 Completion→Retirement→Link→Object 未传 lease。Link/Retirement Store effect 跨独立提交，真实 DB 未迁移，Host flag 未启用。

## 文件级九步

1. 复习 `pipeline_snapshot_group_link_executor.py`、`pipeline_snapshot_group_retirement_executor.py`、`pipeline_snapshot_group_completion.py` 的构造、委派 `_transaction` 与 Store effect，核 W5c5y 已有下层约束。
2. 本方案先提交。仅在 Link、Retirement 构造器加可选精确 `OptInHostLease` 并向下传，Completion 已有的同 lease 向 Retirement 传；新增 `test_a0v_w5c5z_top_group_lease_propagation_pg.py`，更新 W5c5r 静态合同。Store、Host flag、真实 DB 不改。
3. 默认 None 不变；显式 opt-in 时顶层至 ingress 同一 holder，逐笔 metadata 事务 guard，Attempt 心跳/settle 同 lease。不能把多笔事务与外部 Store effect 说成原子排他。
4. 隔离 PG 覆盖构造传递、默认、有效及失权后的 top→bottom metadata 拒绝；旧 Link/Retirement/Completion 无 effect 定向如实记录。
5. W5c5k–z 围栏/结构累计回归，跳过/超时债独立披露，停隔离 PG。
6. 浏览器只读核 A0-V rev4 disabled，不保存/运行/冲刷队列。
7. 只读真实门禁；全面复审 Store 影响窗口与真实迁移/Host flag 未启用，不执行旧组关闭。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文和 Prime 独立受管记忆并读回。
9. 下一波 W5c6a：梳理跨 Store effect 的 fail-closed epoch 校验/回执边界，先做无效应方案与专项合同，不以本波链路传递替代实际排他证明。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。

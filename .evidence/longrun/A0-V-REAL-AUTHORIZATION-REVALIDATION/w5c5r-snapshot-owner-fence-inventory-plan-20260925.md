# W5c5r Snapshot Owner 全链路围栏盘点方案（2026-09-25）

上位 W5c5h–W5c5q。W5c5q 仅给 Attempt 心跳/settle 可选围栏；`PipelineSnapshotGroupCompletion.complete` 的 attempt claim 先在独立外层事务提交，然后才发生 Store 外部执行。下层 Object/Link/Retirement 多次独立事务及 Store effect 不能靠这一笔 claim guard 代替。真实库仍 `a0v_092`，Host flag off。

## 文件级九步

1. 复习 Completion→Retirement→Link→Object→Single ingress 的 `_transaction` 委派与外部 Store effect 提交边界，区分租约可保护 DB 与不可回滚的 Store effect。
2. 本方案；本波只新增可复核的 `test_a0v_w5c5r_snapshot_fence_inventory.py` 作为静态结构性防误报合同、verification；不改生产执行路径，因为尚未证实这些事务采用 `aos_runtime` 登录且 `a0v_094` 可调用。
3. 最小实现：测试固定 claim-before-attempt、上游委派链、至少三类独立 Store effect、W5c5q 默认未接入 Completion；任何未来代码改变须先更新方案与 test。
4. 专项静态合同与现有 Completion/Attempt 单测；不读商城源行、不调用真实执行。
5. W5c3–W5c5r 累计回归分组，隔离 PG 用后停用。
6. 浏览器只读核 A0-V rev4 disabled；不保存/运行/冲刷队列。
7. 输出精确下一步：先在隔离 PG 证明 Completion 事务采用可调用 guard 的 `aos_runtime`，再考虑给整个委派链逐事务接线；Store 外部 effect/未知提交仍需独立方案。真实 Host/DB 不启用。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c5s：隔离 PG 验证 Completion 原始 metadata connector 的 role/事务身份与 Worker fence 兼容性；若不兼容，设计专用 metadata fence，不以 runtime role 冒充。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。

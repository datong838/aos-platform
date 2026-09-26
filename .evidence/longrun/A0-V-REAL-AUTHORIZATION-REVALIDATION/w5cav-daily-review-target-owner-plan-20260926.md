# W5cav｜内容评审后首个真实目标 DailyReview Owner（施工前）

## 上位方案与现场

- 231-5 §1/§4/§5/§7：人工 Review 后自动续跑，任务终态与有来源效果观察后才可能完成首链；反馈需 resultReceipt 幂等、同一安装代次、旧 epoch 禁入、独立目标 Receipt 回读。栖月汇产品 §9 的 EffectReview 需真实经营观察，不能把内容已审核文案算作销量提升。
- m1 `d184245b` 的 W5cau 只给正式 Worker 提供 `claim_current` 原点门。原 `ContentReviewHostService` 已 enqueue `daily_review`、`improvement_observation`、`memory_candidate` 三段，目标均未接线。当前唯一 Alembic head `a0v_098`。

## 本波范围与文件

1. 新增 `services/aos-api/alembic/versions/a0v_099_ecommerce_daily_review_target.py`：租户 RLS、不可变目标/Receipt、stable targetId 与 commandId 幂等唯一；只授权 `aos_runtime` 调用受约束函数，不给表直接 INSERT；SQL 层验当前 claim、同租户、Review 原点当前代次和无外部效果。
2. 新增 `services/aos-api/aos_api/ecommerce_growth_daily_review_target.py`：同一 Runtime 事务中，先 `claim_current`、核对首段 `daily_review`、写前二次 `require_current_origin`，调用持久目标 Owner、独立读回 exact Receipt、调用原 feedback ack 并回读 checkpoint 后才提交。目标只记录“评审通过、效果待观察”的内部事实，绝不创建 EffectReview、Wiki 正式条目或新 Task。
3. 新增 `services/aos-api/tests/extension_runtime/test_ecommerce_growth_daily_review_target.py` 与隔离 PG 测试：先 RED，覆盖同键重放、跨租户/旧 epoch/禁入、断点回滚、目标 Receipt 与 ack、不能误执行后三段/RETURN。必要时最小改现有反馈端口以向 Owner 提供严格 readback。
4. 复核相邻测试、Alembic head、`git diff --check`。本波不启用生产 worker、不应用迁移到真实库、不调用 Provider/商城源；当前实例缺权限时只阻断活体验收。

## 完成与停止条件

- 必须证明 target 写入与 feedback ack 在同一个事务、失败回滚不会留下伪完成；目标 Receipt 可由独立读取函数重建，不能单靠调用返回值。
- 若旧 claim 结果未知或真正目标是否写入不明，只读对账，绝不直接再次执行。PG 隔离测试与真实安装验收分别报告，不得互代。
- 本波验证文件落盘、m1 精确提交、D-waves/AOS 上下文/Prime 状态对账后自动进入 W5caw。施工中确认 `run_one` 只有精确命令入口、没有生产有界 selector/进程生命周期，因此 W5caw 先补自然反馈认领/启停与真实效果观察的 `improvement_observation`→EffectReview 来源门；不能把可手动调用的内部方法称作自动续跑。

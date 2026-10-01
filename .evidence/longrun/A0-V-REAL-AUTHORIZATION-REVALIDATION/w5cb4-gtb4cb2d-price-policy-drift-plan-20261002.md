# GT-b4c-b2d｜原 Model 批准后 Price/Policy 正式 head 漂移禁入

基线 2026-10-02 约 05:05 CST，AOS-001094 / m1 `5fcc5926`。复习 231-5 §5–6、D-waves GT-b4c-b2d、原 ModelEvalRequest/Action 与预算 hold。当前权威库118只读；仅 disposable PG 写测试。今日118→134克隆恢复已 GREEN，但不是当前迁移/重启。

## 精确范围

原 `AipModelEvalBudgetReservationStore.hold` 经 `ModelEvalActionGuard.check_proposal` 重跑 `AipModelEvalRequestStore.require_current`，该读者要求 Provider/Price/Quota/Budget 的精确 head。需要证明**审批后、hold前**通过原 Store 合法发布的新 Price head 或 BudgetPolicy head 会使旧 Eval 批准无法占预算，而不依赖直接篡改表或伪造 ApprovalEvent。

## 文件级计划

1. 只扩展 `services/aos-api/tests/aip/test_model_eval_budget_reservation_pg.py`：复用既有 `seeded_approved_model_eval_request` 原持久申请与 maker/checker；Price 分支经 `AipModelRuntimeStore.publish_price_snapshot` 发布同 ID 新 revision；Policy 分支经 `AipModelGovernancePolicyStore.publish_budget` 发布同 ID 新 draft revision（active 需独立批准，不用测试捷径）。
2. 两种漂移后调用原 Eval hold，均须 fail-closed，Eval hold 行和共享桶占额为零。若 RED，先定位是原申请读者、Action guard 还是预算 writer；只改真实缺口，不复制 head 校验。未漂移的正向与相邻回归一起运行。
3. 专项、相邻、静态、逻辑方案复审、verification、m1精确提交及AOS/Prime/D-waves同步。浏览器对此隔离后端防护测试不适用。

## 明确未覆盖

本波测试只证明 head 漂移负向；不证明自然时间到期、已发出 unknown 账本状态或合法普通 Task/Eval 并发。普通首链当前缺自然来源，不以直接写桶或替代来源造正向。Host/worker/Provider、真实库、旧12 Run、商城源及230 L0均不触碰。

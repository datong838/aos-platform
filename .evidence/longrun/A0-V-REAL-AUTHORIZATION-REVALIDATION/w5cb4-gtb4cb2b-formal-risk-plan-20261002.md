# GT-b4c-b2b｜正式开发风险含 Eval 预留的 PG 验证方案

基线 2026-10-02 04:24 CST，AOS-001091 / `m1 4cea78e4`。复习 231-5 §6、228 模型容量/成本、GT-b4c-b 方案，以及 `test_budget_cost_{issuer,consumer,configuration}_pg.py` 的正式签名批准/消费/派生路径和 `test_model_eval_request_pg.py` 的原 Model 申请/Action。当前真实库 a0v118 只读；本波只在自动创建并销毁的 disposable PG 验证。

## 精确发现

普通 `AipBudgetReservationStore.reserve` 强制真实 Task、原审批和非空 `action_binding_hash`；通用 Action 的普通草案没有绑定 hash，首条内容生成又有自然来源门。既有 `test_content_first_action_budget_pg.py` 只证明未绑定拒绝，不能拿直接 INSERT `aip_budget_bucket` 伪装普通业务正向。正式费用门现有测试有签名 checker 决策→预算激活→派生 `BudgetPolicy/Price`，可独立先证明 GT-b4c-b2a 的真实 Eval hold 被 `DevelopmentRiskProposal` 的 `max_requests/total_risk_minor` 计入。普通与 Eval 的完整并发正向仍需当前正式 Action 绑定来源，不因它缺失而阻断此独立验证。

## 文件级计划和 RED

1. 仅扩展 `services/aos-api/tests/aip/test_model_eval_request_pg.py` 已有 PG helper：允许调用者注入**由原正式预算签名消费及配置派生的** BudgetRevision/BudgetPolicy/Price/Provider；默认 fixture 与全部原断言不变，不复制 Model 申请和 Action 造数，不改生产 API。
2. 在 `services/aos-api/tests/aip/test_model_eval_budget_reservation_pg.py` 添加正式风险测试：用原 `case`/`produce_formal_provider`/`BudgetCostProposalStore`/签名 `BudgetCostIssuer`/受限 consumer 产生 `max_requests=1,total_risk=per_request` 的预算，调用原配置派生得到当前 Policy/Price；原 Model request 和 checker 批准后用 b2a writer hold 一次。再调用 `require_cost_risk(new_hold=True)` 必须拒绝，`new_hold=False` 必须通过。先跑 RED，定位失败是 fixture、来源还是生产风险逻辑，不通过改宽门实现绿色。撤回/过期与 Policy/Price 后续漂移另作后续子步；本波不借静态合同检查宣称运行中撤回已验证。
2a. 正式价格授权同时绑定精确 Provider 和 `providerModelId`；b2a writer 现仅经原申请复验 Model 的 Provider/Price 引用，尚未比较 Price 的开发费用授权与源 Model 的 `providerModelId`、BudgetPolicy 开发费用授权。测试加入错模型 ID RED；只在 `services/aos-api/aos_api/aip_model_eval_budget_reservation.py` 该持久源交点做最小 fail-closed 校验，同时拒绝 Policy/Price 费用授权不一致，防止不同模型共享一个已批准费用额度。独立的 Policy/Price 漂移注入测试留到后续子步。
3. 若代码现有合并查询可通过，仅保留测试和必要 fixture 提取；专项与正式费用门/原 Model 申请相邻回归、复审、verification。实际业务普通 Task/Eval 并发由下一独立子步继续，不能把本波的正式风险测试冒充它。

## 出口

通过标准为正式签名批准消费来源与原 Model 申请/审批共存，Eval hold 后正式风险上限拒绝新 hold，`new_hold=False` 在未撤回时可重验；数据均为 disposable PG。无 Provider call、Intent、当前库迁移、自然首链或发布决定。

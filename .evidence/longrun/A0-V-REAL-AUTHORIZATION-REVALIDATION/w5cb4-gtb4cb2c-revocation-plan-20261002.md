# GT-b4c-b2c｜正式费用撤回后 Eval 新占额禁入计划

基线 2026-10-02 04:40 CST，AOS-001092 / `m1 3560293a`。复习 231-5 §5–6、GT-b4c-b2b 方案/验证、`test_budget_cost_issuer_pg.py` 的 maker 撤回及 `test_content_first_action_{budget,binding}_pg.py` 的真实普通路径边界。当前真实库 a0v118 只读，代码 a0v134；本波只运行 disposable PG。

## 已核实的普通路径边界

`test_content_first_action_budget_pg.py` 的通用 Action 有真实 Task/Run 和原 maker/checker，但 `action_binding_hash=None`，原预算 Store 拒绝；`test_content_first_action_binding_pg.py` 的绑定由原 Store 生成，不过业务源准备显式替代，且测试断言自然 intent 门拒绝普通预算占额。不得借这两者宣称真普通 Task/Eval 并发正向。本子步只覆盖正式费用撤回与 Eval 账本，普通路径继续登记待合法来源。

## 文件级步骤

1. 仅扩展 `services/aos-api/tests/aip/test_model_eval_budget_reservation_pg.py` 上一波正式签名费用参数化用例：设置可容纳两笔的 `max_requests=2,total_risk_minor=2×per_request`，先持久 hold 一笔，核撤回前第二笔在风险额度内；经原 `BudgetCostIssuer` 用 maker 正式撤回。
2. 撤回后用新的原 ModelEvalRequest 与 maker/checker 审批尝试第二笔 hold：必须失败封闭，第二笔无 hold 行，第一笔和三个桶的占额不释放；原已占额的 idempotent 对账不得新占额或调用 Provider。若测试 RED，定位是当前费用门还是既有 hold 重入顺序，只做最小修复。
3. 跑本专项及相邻预算/费用门回归，静态与方案复审；verification、精确提交、上下文及 D-waves 更新。未覆盖时间流逝的自然到期和独立 Policy/Price 漂移，本波不能宣称 GT-b4c-b2 全部完成。

## 安全界

无真实库写入、无 Provider/Host/worker、无 Intent 或外部效果，不制造普通 Task/AgentRun 或直接修改桶。`org-org/dev-project` 仅作为 disposable PG 正向，`dev-org` 继续零副作用 canary。

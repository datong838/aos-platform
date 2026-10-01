# GT-b4c-a Model 首评共用预算账户合同

基线 2026-10-02 03:35 CST；AOS-001088 / `m1 8a429017`。用户已批准 Model 首评用途设计、代码及隔离验证；当前真库只读 a0v_118，Provider/Host 禁入。复习 231-5 第6节、228 AIP 模型容量与成本治理、BG00GT、GT-b4a 方案/RED，读原 `aip_budget_reservation_{contracts,store}.py` 和 `BudgetPolicyRevision`。

## 源码与方案约束

- 普通预算调用的 `ReserveBudgetRequest.policy_ref` 必须是真 `BudgetRevision`；`derive_bucket_authorities` 以其 `resource_id` 生成日/月稳定账户。普通 task-kind 桶身份为 `operation_id:task_id`。
- Model 首评申请引用 `BudgetPolicyRevision`，该不可变政策内含精确 `BudgetRevision`。首评没有 Task，不能调用普通 `ReserveBudgetRequest` 伪造 Task，也不能用 Model 的 BudgetPolicy ID 开另一份日/月限额。
- 同租户、同 `BudgetRevision`、同日期/月份的首评与普通业务，必须产生**完全相同**的日/月 `BudgetBucketAuthority`；首评申请上界独占第三个 task-kind 账户 `model-eval/<request_id>`。首评 ID 禁含 `:`，使该账户不可能与普通 `operation_id:task_id` 撞名。原 `aip_budget_bucket` 是共同锁与占额目标；本波只实现身份派生合同，不写占额。

## 文件级计划与 RED

1. 先新增 `services/aos-api/tests/aip/test_model_eval_budget_bucket_contract.py`：同 BudgetRevision 下首评/普通业务日/月键、期间与限额相同，首评 task-kind 与真 Task 不碰撞；不同 BudgetRevision、跨月与过期/伪 ID fail closed。未实现时应 ImportError RED。
2. 最小修改 `services/aos-api/aos_api/aip_budget_reservation_contracts.py`：抽出原三桶时间/账户公共计算核；原 `derive_bucket_authorities` 保持精确输出，新 `derive_model_eval_bucket_authorities` 只接受明确 ModelEvalRequest ID、真 BudgetRevision ref 与上界，不构造 `Task`。不得动普通 Store 的 Task/审批约束。
3. 专项与原预算合同相邻回归、静态检查、方案自洽/风险复审，verification 落盘后 m1 精确提交并同步 01/06、Prime 与 D-wave。

## 出口与后续

本波完成只证明稳定预算账户合同；`aip_budget_bucket` 占额、独立申请/原 ApprovalEvent 复验、与物理容量同事务、一次 Intent 和费用状态机仍是 GT-b4c 后续。正式 Provider 物理额度来源仍未建立，故真实发送为零。不得把本合同的测试 GREEN 称作预算/首链完成。

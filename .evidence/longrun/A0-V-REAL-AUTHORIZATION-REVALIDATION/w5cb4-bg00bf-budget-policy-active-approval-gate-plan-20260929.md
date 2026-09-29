# W5CB4 BG-00bf｜BudgetPolicy 新 active 审批禁入

依 231/231-9、BG-00aw/BG-00be：BudgetRevision active 已由独立审批/外部用量门禁入，但 BudgetPolicy 自身 `approvalRef` 仍仅字符串。隔离测试能给 active BudgetRevision 既存行，因此需单独证明 BudgetPolicy 新 active 不会越过 maker/checker。当前真实库只读、Host/worker/Provider关闭。

文件级：`tests/aip/test_aip_model_governance_policy_store.py` 先在隔离 PG RED 复现仅 `approval:test` 的新 active BudgetPolicy 受理，断言拒绝无行；`aip_model_governance_policy_store.py` 在同请求 Receipt replay 后、新写入与依赖检查前拒绝新 active BudgetPolicy；`routers/aip_model_governance_policies.py` 映射 422。保持 draft 的精确 active BudgetRevision 依赖校验、既存 BudgetPolicy active 读取与 Quota 已有门；必要时只改 test-only 既存行夹具。专项/相邻回归、diff/编译及方案复审后提交、同步上下文和清单；正式预算激活与审批来源不在本波伪造。

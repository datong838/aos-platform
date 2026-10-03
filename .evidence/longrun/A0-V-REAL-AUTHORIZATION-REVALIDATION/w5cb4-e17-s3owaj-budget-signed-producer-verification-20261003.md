# E17-s3o-w-aj：受限预算来源与 Binding 只读联测

按 `231-9`、BIND-1 和 s3o-w-aj 文件级方案，在可销毁测试 PG 使用原 `approved→consume→derive` 受限链：正式表形状产生 BudgetRevision + PriceSnapshot + BudgetPolicyRevision；原配置返回 `activationEligible=false`。这是隔离合同测试，不是当前 `org-org/dev-project` 正式供应商/模型/评测/预算已发布。

新增 `test_signed_budget_policy_is_exact_for_binding_readiness_and_tenant_isolated` 直接将原派生 Receipt 的 `policyRef` 交给 `PostgresBindingDependencyAuthority(connect_read_only)`：现时 exact active 读取 true；`dev-org/dev-project` false；在 `effective_until` 边界 false；错 revision false；隔离库 owner 改 head 当前修订后旧 ref false。正向和负向均读取真实迁移表、RLS 范围，未用假的 `ModelStore` 来冒充预算来源。

| 验证 | 结果 |
| --- | --- |
| 新隔离 PG 精确测试 | 1 passed，退出0。 |
| 原预算配置整文件 + Binding readiness 相邻 | 28 passed，退出0。 |
| `py_compile` 与 `git diff --check` | 退出0。 |

复审：`AipModelGovernancePolicyStore.require_exact_active` 还核下层 BudgetRevision、hardStop、unknownUsage 和窗口；Route resolver 的模型治理路径调用该原门。当前新查询额外要求 BudgetPolicy 为 head 当前修订。未改生产代码、迁移、真库、API/Web 进程；不需要再次重启质量门。当前正式 Provider/Route/Eval/License/预算签发身份及六 Binding仍未证，Host/worker/Provider关闭，首链 pending。

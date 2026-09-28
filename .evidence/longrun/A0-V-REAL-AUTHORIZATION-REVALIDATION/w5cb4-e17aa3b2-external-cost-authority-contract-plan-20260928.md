# W5CB4 E17-aa3b2｜预算激活的价格与外部费用权威合同

## 上位方案与当下事实

231-5 §6 要求批准价格版本、输入计量与最大输出/时长/数量推导本次最坏费用；未知账单保留占额，只能只读对账，不能超时自动释放。231-9 要求产品价格与经营成本未知不可写零。这里讨论的是 **AIP Provider 费用权威**，不是商城商品/佣金价格，不能混用。

当前代码：`aip_budget_reservation_store.py::_price_authority` 要求同租户 ACTIVE exact `ModelPriceSnapshotRevision`、有效期与哈希；`_usage_authority` 要求与 invocation/provider 结果绑定的 measured `UsageReceipt`；`_actual_from_usage` 用当前精确价格计算整数 minor 单位费用。`aip_model_runtime_contracts.py` 的 development cost authorization 可声明 deferred、无数值价格，仅限 development；它不能充当生产可执行费用上界。预算激活 Preview/Decision 当前只有内部账本与 `external_usage_proven=false CHECK(false)`，没有可核验的外部账单归属、账期、货币、未结负债及双人正式批准。

2026-09-28 当前权威库 `aos_current_preview_20260927@a0v_111` 使用 READ ONLY 查询：`org-org/dev-project` 的 ModelPriceSnapshot Head/Revision、UsageReceipt、BudgetReservation、BudgetBucket、BudgetUsageSettlement、Budget Head 均为 0。无权从历史试点价或合同示例补数，不读商城源。

## 文件级施工边界

本波先制定当前可核验合同，不做 active 写入或迁移：

1. 价格来源：必须由正式 ModelRuntime Owner 发布 ACTIVE、同租户、精确 revision/hash、有效窗口的 ModelPriceSnapshot；数值字段和 token 单位完整，route/model/provider exact 对应；deferred price 只用于明示开发费用政策，不能作“零成本”生产授权。当前实例 Head 为 0，保持阻断。
2. 使用与账单来源：内部 UsageReceipt/Reservation/Settlement 是 AOS 用量账本，尚不能单独证明 Provider 外部账单全量及负债为零。正式外部来源须包含 provider account、账期截止、货币、最终/未决状态、总额、查询时点、签名或可信抓取 Receipt、归属租户与不可变 hash；未知结果保留最大敞口。当前没有该 Owner/来源，不能把 `external_usage_proven` 改 true。
3. 费用上界：从 exact 价格、输入 token 上限、输出 token/时长/数量硬上限求整数 minor 最坏值，并同 Task/日/试点桶及 approved Budget revision 比较；无可执行上界则不自然调用。消费者必须在同事务重新核 Decision 当前性、Revocation、Budget Head 与来源引用，再以唯一键写 active Revision/消费 Receipt；单独 precheck 不是授权。
4. 只在上述来源和正式第二 checker 实际齐备后，另波设计 a0v_112+ DB gate、迁移及独立备份/完整克隆/零执行切换。此波无 HTTP、无 Provider、无 Host、无写当前库。

## 退出/下一步

只读来源矩阵与缺口证据落盘；下一波优先做 BG-00 当前正式来源及绑定产品链的可独立最小实现。预算消费正向继续等待合法 Owner、外部费用来源和双人授权，不能以历史样例或模拟证明取代。

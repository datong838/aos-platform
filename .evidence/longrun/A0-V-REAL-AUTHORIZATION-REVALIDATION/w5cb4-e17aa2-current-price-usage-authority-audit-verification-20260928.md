# W5CB4 E17-aa2 当前价格、上界与外部费用权威只读核验

## 身份、方法与输出

- `m1@a0a472b3`、authority `AOS-000842` 起步；按文件级方案复习 231-5 §6。当前 API 重载后签名预检通过：库 `aos_current_preview_20260927@a0v_110`、唯一安装 approved、4 published、binding0。连接后 `read_only=True` 并断言库名/版本；仅参数化统计 `org-org/dev-project`，未读商城源或用量 payload。
- 只读命令退出 0：`aip_model_price_snapshot_head/revision`、`aip_budget_head/revision`、`aip_budget_reservation`、`aip_budget_reservation_bucket`、`aip_budget_bucket`、`aip_budget_usage_settlement`、`aip_capability_invocation`、`aip_usage_receipt`、`aip_action_usage`、`aip_budget_activation_preview/decision` 全为 0。真实租户仍只有一名正式 owner（E17-z 读回）。空 AOS 表不等于第三方账单已对账。
- 在当前库只读列关系名，`bill/invoice/reconcil/provider_usage` 模式只命中三张 Action 人工对账关系；没有识别出当前预算外部账单完整性权威。关系名扫描只能证明本库没有明显命名的正式账单关系，不能证明外部系统没有账单。

## 代码合同对账

| 要求 | 当前证据 | 判定 |
|---|---|---|
| 当前已批准价格版本 | 当前租户 `aip_model_price_snapshot_revision=0`；`AipBudgetReservationStore._price_authority` 要 exact active、hash、租户、期间、CNY | NO |
| 可执行费用上界 | `ReserveBudgetRequest.upper_bound_minor` 是调用输入；预留 Store 核对 ActionDraft `budgetUpperBoundMinor` 与其相等、再锁三桶核已占额；当前 `ecommerce_growth_runtime_adapters._budget_request` 从命令 `upperBoundFen` 取值。未证明其由已批准价格与最大输入/输出/时长计算 | UNKNOWN／生产者缺口 |
| 内部已占额/unknown | 当前 Reservation/Bucket/Invocation 全 0；Store 算 `held+submitted+settled+unknown`，未知不自动释放 | 当前 AOS 内部空，不能外推 |
| 调用后实测 | `aip_provider_usage_bridge.py` 从 Provider 响应 ingest UsageReceipt；settle 要 exact measured receipt、Provider result hash 与价格复核。当前 UsageReceipt/Settlement=0 | NO 当前实测 |
| 外部账单完整性/对账 | 本库没有找到当前预算账单完整性来源；仅表名扫描和代码审计，不能替代第三方权威核验 | UNKNOWN |
| 独立正式 checker | 当前真实租户仅 `owner:1` | NO |

## 结论与下一门

`externalUsageProven=false` 与 `activationEligible=false` 保持，公开 active 422、Host/worker 0；当前实例不可正向批准或激活预算。不得用空账本、历史价格、测试 fixture、人工口头金额或客户端布尔值填补缺口。下一波 E17-aa3 的独立代码项可先实现**只接受正式证据的 DB 级单次消费合同与失败封闭负例**，但不得开放当前实例正向发布；费用/价格生产者和正式 checker 需独立授权来源。无当前库写、Provider 调用、商城源读取、旧 Run 重放、手工 Run 或 `dev-org` 写。

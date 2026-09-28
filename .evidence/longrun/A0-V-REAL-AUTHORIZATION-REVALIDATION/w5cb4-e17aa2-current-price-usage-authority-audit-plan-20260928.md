# W5CB4 E17-aa2｜当前价格、计量上界与外部费用权威只读核验方案

## 上位规则与目标

231-5 §6 要求已批准价格版本、输入计量、最大输出/时长/数量来计算可执行费用上界，held/submitted/unknown 均占风险额度，外部账单仍须对账；没有上界不得自动调用。E17-y2 预览已固定 `externalUsageProven=false`，E17-aa1 直接 active 发布已禁入。当前库 `aos_current_preview_20260927@a0v_110`，正式成员一名 owner；本波只查事实，不造批准或用量。

## 只读步骤与证据

1. 先重验 m1、权威卷、签名安装与迁移；连接后立即 `read_only=True`，断言库名/版本。只看 `org-org/dev-project` 的价格 Head/Revision、预算修订与 Reservation/Bucket/Settlement、Capability Invocation、UsageReceipt、Action 用量的计数和非敏感状态汇总，不读取商城源或敏感 payload；同时检查是否存在正式外部账单/对账关系及来源声明。
2. 代码审计 `aip_model_runtime_store.py` 的价格精确读、`aip_budget_reservation_store.py` 的 upper bound/unknown/settle、`aip_provider_usage_bridge.py` 的 Provider Receipt ingest；明确哪些是**调用后的计量**，哪些能证明调用前最大风险，哪些仅 AOS 内部账本。必要时读现有产品方案中费用批准与责任主体，不能推定空表代表账单归零。
3. 产出判定矩阵：当前真实价格版本/上界输入/外部账单完整性/unknown 对账/独立审批主体逐项 YES/NO/UNKNOWN，记录可复核查询与退出码。缺任何正式证据继续 `externalUsageProven=false`、active 422、Host 0；独立代码项另立 E17-aa3 文件级计划，不用临时账号或测试值作当前权威。

本波预期为只读事实审计；若找到可修复代码缺口，先追加文件级计划和 RED，避免把本波变成大范围预算重写。收口更新 verification、D-waves、上下文与 Prime，m1 精确提交，不 push。

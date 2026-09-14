# SC4-5c1 已完成事件的历史引用

2026-09-14，基线64689154，m1，不push。

实际record_target_receipt把claimed事件改accepted并释放claim，原Occurrence摘要含status，旧恢复revalidate因此失败。恢复场景新增历史引用读取：当前accepted且无claim、唯一receipt_recorded attempt、Occurrence/attempt同目标Receipt、实际原AnalysisRuntimeReceipt可按精确引用和原幂等键回读且正文hash正确，才校验历史claimed投影。原事件其他字段必须与原回执摘要一致。START不变，不修改旧hash/状态，不制造Claim。

红：实际完成事件后analysis occurrence lineage drifted。绿：实际完成事件可继续前置校验，但无Fulfillment仍拒绝；完成attempt回执错接或事件deadline变化均拒绝并回滚测试变化。累计51 passed/7既有警告/32.22s，覆盖当前数据准备、分析Host、formal START与原数据续跑。AR2 1905/184/93五数组空，memory GREEN 1101/1084/2701，diff check通过。

全部隔离临时PG，来源/能力依赖fixture。没有主租户变更/模型调用/实际续跑。下一c2建立已完成原事件的当前来源上下文，避免复用已结束租约；再专用恢复门和已有D01/D02/D03真实Worker衔接。实际Worker已有独立输入/披露/方法/指标校验，应复用，不能以初始化Context冒充经营事实。

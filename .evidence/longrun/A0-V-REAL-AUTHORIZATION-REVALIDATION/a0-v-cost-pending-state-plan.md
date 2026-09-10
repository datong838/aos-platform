# 业务完成与费用待核算状态

先修改 `services/aos-api/aos_api/aip_budget_reservation_contracts.py` 和 `services/aos-api/tests/aip/test_aip_budget_reservation_contracts.py`，新增 cost_pending：必须存在请求 Receipt、完成 Provider Receipt、非空唯一 UsageReceipt，actualMinor 必须 null。此状态表示 Provider 结果与用量已知，仅金额未知；不能复用 unknown（其含义为执行结果未知），也不能填 settled=0。

后续同一施工串需新增前向 SQL 迁移，显式允许 submitted/unknown→cost_pending 和 cost_pending→settled；禁止 cost_pending 再 submitted/released，不能因核价重发 Provider。必须保持原身份不可变、revision+1、hash 变化和时间不倒退。Bucket 仍保留原已提交占用至核价，不能将它写成已结算金额；开发授权的成本放行与商业额度计算需要明确区分，不能把开发费用永久占用商业预算作为完成实现。

本次合同修改不创建运行入口，SQL 仍不接受该新状态，因而不能提前激活新流程。完成 Store、迁移与依赖接线后以隔离数据库证明恢复/重复用量/跨租户/未知结果和账后核价不触发 Provider。本卡不声称第一步就是整体完成。

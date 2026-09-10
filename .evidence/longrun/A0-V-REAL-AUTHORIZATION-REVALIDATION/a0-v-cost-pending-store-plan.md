# 费用待核算 Store 接线

修改 services/aos-api/aos_api/aip_budget_reservation_store.py，新增 complete_cost_pending。输入仅现有 reservation ID、Provider 结果 hash、UsageReceipt/Evidence refs 和 actor；不接收单价或金额。锁定原 reservation；同内容 pending 回读，不同内容冲突；只有 submitted/unknown 可转换。

转换前在同事务读取 exact active price authority，其 developmentCostAuthorization 必须存在，与租户、提交 Receipt 的 exact Provider 和当前时间匹配。模型与价格绑定由既有 Host 的 exact Model/Price 检查保证；本 Store 不发起 Provider 请求。逐个复用 _usage_authority 验证实测用量与当前 invocation/result hash，再写 completed Provider Receipt、cost_pending Reservation 和 completed Invocation。

本步不释放预算桶、不填写 settledMinor、不写结算表；商业预算不能被“待核算”伪释放。开发额度与金额结算后续联动，未完成前不开放新 active 价格。针对性测试验证状态/重复回执/漂移/权限失败前无写入；之后还须完整隔离 PG 集成，不能以替身测试代替。

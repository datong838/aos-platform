# 开发授权接入预算策略 Owner

修改 `services/aos-api/aos_api/aip_model_governance_policy_contracts.py`，测试 `services/aos-api/tests/aip/test_aip_model_governance_policy_contracts.py`。

BudgetPolicy 增加可选 developmentCostAuthorization，默认完全不序列化，确保旧正文/hash 保持一致。非空时加入既有 materialize_policy 内容哈希及持久化 payload；批准依据必须与父策略一致，父策略时间窗口不能超出授权，正式 Revision 的租户必须一致。禁止与 zero-price 授权混用。

本切片仅接入持久化合同，unknownPriceBehavior 仍为 block，未完成 Resolver/结算前不打开执行路径。测试旧字段集合/hash、授权内容参与 hash、跨租户 materialize 拒绝、批准/时间漂移与默认 roundtrip。先新增测试，再最小实现。

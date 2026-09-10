# 未核价模型记录施工卡

修改 `services/aos-api/aos_api/aip_model_runtime_contracts.py` 和 `services/aos-api/tests/aip/test_aip_model_runtime_contracts.py`。ModelPriceSnapshotRevision 加可选 developmentCostAuthorization；未提供时完全沿用旧校验和序列化，提供时输入/输出/缓存价格全部必须 null、币种 CNY、租户与授权相同、有效期有时区且不超过授权。

本切片仅允许 deferred 记录处于 draft/validated，不允许 active，以避免旧 Resolver 在联合校验和费用结算接线未完时把它当可执行价格。下一切片将 active 放行条件迁移到正式策略/模型联合 Owner 校验后，再开放运行。此约束只针对新增 deferred 记录，旧 active 价格不受影响。

测试先验证 deferred accepted、零价混入拒绝、跨租户/过期窗口拒绝、active 拒绝和旧正文哈希稳定。未部署、未迁移、无真实调用。

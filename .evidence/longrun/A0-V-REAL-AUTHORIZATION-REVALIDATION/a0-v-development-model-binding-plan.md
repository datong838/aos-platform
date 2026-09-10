# 开发授权与模型联合依赖校验

修改 services/aos-api/aos_api/aip_model_governance_policy_store.py 的 require_model_dependencies；新增 services/aos-api/tests/aip/test_aip_development_model_binding.py。

既有 Model Store 发布和 ExactProviderInvoker 调用前均经过该方法。先按原路径回读 exact active quota/budget，再取持久化预算策略中的 developmentCostAuthorization；存在时精确匹配当前租户、Provider ref、provider_model_id、父策略 approvalRef 与当前时间。失败转换为现有 ModelGovernancePolicyDependencyBlocked，禁止泄露输入正文。无授权的旧策略行为保持原状。

验证采用纯依赖替身，不访问 DB，覆盖全部漂移、旧调用兼容以及确实读取两条 exact refs。此步骤只收紧已声明的授权范围，不开放未核价 active 价格或修改结算。

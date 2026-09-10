# 模型发布与路由选择接入治理 Owner

基线 e178b253。延续开发费用延后核算施工卡，不改变真实首链目标。已完成调用器联检，本步让发布和 READY 判断使用同一个治理 Owner，而非等到发送前才发现开发授权错绑。

修改目录 services/aos-api/aos_api：aip_model_runtime_store.py 新增对已读 exact 价格和当前策略的联合校验入口，publish_model 调用；aip_model_runtime_resolver.py 在候选价格检查后调用该入口；aip_model_governance_policy_store.py 将同一判定时刻贯穿配额/预算/开发授权。

测试目录 services/aos-api/tests/aip：新增 test_a0v_model_readiness_governance.py，更新 test_aip_model_runtime_resolver.py 的显式测试替身和 test_aip_development_model_binding.py 的时钟接口。覆盖发布不得写入不匹配授权、价格 scope/ref、有效期、Resolver 不可返回假 READY，以及旧文本合同回归。

模型 ACTIVE 要求绑定价格 ACTIVE 且当前有效；非 active 模型继续允许 staged 价格，保留原有编排步骤。deferred ACTIVE 合同禁入本步仍不解除，须等业务结果承接能记录 cost_pending。无真实模型请求、无业务库写入；测试仅隔离替身。回滚回退本步代码，不改变已存不可变对象。退出须新鲜测试与记录，不把本步标成真实首链完成。

# 调用前价格记录与开发授权联检

基线 37f141b8，延续 development-deferred-cost 施工卡第 4 项。用户已承担开发验收费用；不等待报价。预算记录保留真实用量和未知金额。

本切片修复 READY 路由到实际调用之间未回读价格权威的缺口。在 Secret 和 transport 前读取 selectedPriceSnapshot，匹配模型的 priceSnapshotRef、记录 ID/revision/hash、租户、active 状态与调用当下有效期。空引用、过期和错绑一律拒绝。

涉及文件：
- services/aos-api/aos_api/aip_exact_provider_invoker.py
- services/aos-api/aos_api/aip_model_governance_policy_store.py
- services/aos-api/tests/aip/test_aip_exact_provider_invoker.py
- services/aos-api/tests/aip/test_aip_development_model_binding.py

治理 Owner 对显式传入的 deferred 价格记录，要求其开发授权与当前 exact BudgetPolicy 的授权相同；原有模型范围、批准依据和时效检查继续执行。普通已知价格保持旧逻辑。发布和 Resolver 的联检以及 deferred 激活仍属下一步，不在本次解除合同激活禁入。

先添加负例并复现缺口，再最小实现。验证包括价格缺失、引用错绑、哈希漂移、租户、状态、未来/过期有效期及授权不同，均断言 Secret 与 transport 为零；原文本/图片单测回归；视频实际生成与恢复另行验收。无真实 Provider 调用，无数据库或已存在业务数据变更。回滚仅回退新增源码；不要回写不可变 Receipt。

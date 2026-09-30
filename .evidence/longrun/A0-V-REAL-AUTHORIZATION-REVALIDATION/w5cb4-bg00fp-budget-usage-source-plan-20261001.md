# BG00FP 预算用量来源及首次激活依赖审计方案

基线 AOS-001030 / m1@b1d501e4；Task W5CB4-BG00FP-20261001。复习231、231-5§5/6/7、231-9§1/2，E17-y/aa3b1，开发费用授权/策略Owner/模型联合依赖方案，BG00FO。

## 目标与范围
沿首链必要预算配置识别可以复用的正式来源，避免两种错误：把内部无记录当外部已知零费用；把用户已授权的开发费用延期对账误当永久停止开发理由。本波只读审计已有实现、跑相关回归，不新增激活入口、迁移、授权事实或真实费用记录。

## 文件级步骤
1. Read aip_budget_activation_store.py / exposure.py：精确批准、空账本与固定外部证明门；核对预览不可变合同。
2. Read aip_provider_usage_bridge.py、aip_telemetry_usage_service.py、aip_eval_authority_store.py、routers/aip_telemetry_usage.py：记录producer身份、lineage、去重hash覆盖及缺少的稳定预算账户/期间覆盖，区分单次调用凭证和完整对账。
3. Read aip_development_cost_authorization.py、aip_model_governance_policy_contracts.py / store.py、aip_budget_reservation_store.py：确认development授权必须来自已持久化active策略，不能用请求正文自证；跟踪首次BudgetRevision与BudgetPolicy依赖。
4. 执行相关既有合同/Store/预算激活PG测试；纯替身测试只证明代码合同，PG预检使用测试Principal对象亦不等于正式OIDC产品验收。不要启用旧测试模块的独立PG开关，不让其脱离标准隔离库。
5. verification记录逐文件结论、回归命令/退出码、未完成与BG00FQ文件级方向；精确提交本plan和verification。Delivery/CAS/424/D-waves/Prime更新另在docs m1精确提交。

## 下一步决策标准
开发延期授权可复用其scope/provider/model/批准/时效语义和cost_pending账本；不得把它填入external_usage_proven=true。若其生产者依赖尚未active的BudgetRevision，则先冻结独立于active BudgetPolicy的首次费用来源与审批合同，再做Producer。正式来源至少区分完整对账证明与开发风险批准，不能共用真假布尔值伪造外部账单。消费需当前独立checker、稳定账户/期间、exact目标/Head、源hash/撤销/时效、唯一Receipt及同事务边界；正式迁移另波。

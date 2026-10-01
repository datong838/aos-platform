# BG00GQ verification / 2026-10-01

基线 m1 76b0c599 / AOS-001057。Task W5CB4-BG00GQ-FORMAL-PROVIDER-20261001。

## 当前证据

- 开工 memory-status：7 strong CURRENT；validate GREEN /1518 Delivery/1516 Task/4036 events；exit0。
- RED：API目录 `.venv/bin/python -m pytest tests/aip/test_formal_provider_cost_source_pg.py -q`；/tmp/aos-gq-provider-red.log，1 failed/4.61s，Provider原发布Receipt为0。外层tail命令返回0不作为pytest成功证明。
- 首轮四组：/tmp/aos-gq-provider-special.log，29 failed/4 passed/5 errors/26.32s，pytest exit1。原因是正式Egress合同拒绝provider.invalid；改为合同允许的api.agnes-ai.cn，仅保存配置，不连接Provider。
- 原RED复跑：/tmp/aos-gq-provider-green.log，1 passed/5.29s，exit0。通过原JWT认证HTTP、插件Authority、签名Guard及原Store，核原Receipt与两个active2 exact依赖。
- compileall（三个改动测试文件）和git diff --check exit0。一次仓库根误用.venv/bin/python --version返回127，未执行测试；后续均正确API目录。
- 累计26组 /tmp/aos-gq-provider-regression.log 正在执行；没有提前宣称通过。

## 复审与边界

无生产代码/迁移修改；真实当前库未连接/重启。Helper仅注册惰性来源，沿已有独立临时角色/凭据文件和pytest teardown；HTTP无dependency override。短时预算在Provider准备之后发布，原过期/撤销/未知/并发用例逻辑保持。
真实secretRef尚不存在，Provider endpoint只是配置，不证明健康、Eval或调用许可。隔离签名身份不冒充正式客户身份。Model来源完整联合与自然首链继续未完成；不制造健康状态与Eval结果，不启动Host/worker/Provider、不读商城源、不重放旧12Run。
下一项：把原批准派生price/policy、正式Quota/Network接入原Model配置生产入口，明确缺少Eval/Health的真实禁入；再推进Review/AgentRun/首生审批/Capacity/GE held来源。

## 最终累计

/tmp/aos-gq-provider-regression.log：302 passed /7既有warnings /218.79s /pytest exit0；26文件，不与此前专项相加。API目录 `.venv/bin/python -m pytest` 加下列文件与 `-q`：

- tests/aip/test_guard_policy_activation.py
- tests/aip/test_guard_policy_activation_pg.py
- tests/aip/test_aip_policy_activation_action.py
- tests/aip/test_aip_network_policy_action_producer.py
- tests/aip/test_aip_runtime_guard_policy_contracts.py
- tests/aip/test_aip_runtime_guard_policy_store.py
- tests/aip/test_aip_runtime_guard_policy_api.py
- tests/aip/test_aip7_model_runtime_store.py
- tests/aip/test_aip_network_policy_store.py
- tests/aip/test_network_approval_precheck_expiry_pg.py
- tests/aip/test_network_consumer_signed_https_pg.py
- tests/aip/test_network_atomic_consumer_pg.py
- tests/aip/test_network_consumer_actor_pg.py
- tests/aip/test_network_consumer_connection_pg.py
- tests/aip/test_content_first_action_binding.py
- tests/aip/test_content_first_action_binding_pg.py
- tests/aip/test_quota_policy_activation_pg.py
- tests/aip/test_aip_model_governance_policy_store.py
- tests/aip/test_aip_model_governance_policy_contracts.py
- tests/aip/test_aip_model_governance_policy_api.py
- tests/aip/test_budget_configuration_runtime_pg.py
- tests/aip/test_formal_provider_cost_source_pg.py
- tests/aip/test_budget_cost_issuer_pg.py
- tests/aip/test_budget_cost_consumer_pg.py
- tests/aip/test_budget_cost_configuration_pg.py
- tests/aip/test_aip_provider_plugin_authority.py

本波没有UI更改，浏览器不适用。仅正式配置来源的隔离验证收口；模型全来源联合、实际部署/每日重启、自然首链与发布仍未完成。

# BG00GR verification / 2026-10-01

基线97642c33 / AOS-001058；主Task、CATALOG与UI-REVIEW三个精确Task，m1单写不push。

## 实现与证据范围

Model/Route仅draft/validated允许缺失Eval，active/suspended/revoked仍要求exact ref。中央Eval reader对None返回原DependencyBlocked，原active发布即使model_copy也禁入。原HTTP chain-overview缺失Eval节点保持blocked，不能all(empty)变ready。既有非空字段/哈希不变。

新增全迁移临时PG来源联合：真实插件manifest→签名Guard/原HTTP Provider→签名费用决定/低权消费/原price-policy派生→签名Quota/Network→原HTTP Model/Policy/Route。无占位Eval、无手写healthy；缺少Eval/Health返回BLOCKED。Provider secretRef仅opaque未配置引用，不证明真实凭据或外部可用。

SDK严格nullable解析、active缺失拒绝，目录投影同步；路由页validated改“已校验配置”，运行前仍需评测，空Eval历史显示“未评估”。

## 测试记录

- 首次追加RED误用API cwd重复路径，文件未写；该次测试不是RED。修正路径后/tmp/aos-gr-contract-red-r2.log：3 failed/9 passed/4.49s，exit1，两个缺失字段+中央reader AttributeError。
- 首次前端命令缺node，exit127，不算RED。复用已安装Node PATH后/tmp/aos-gr-sdk-red-r2.log为缺失Eval解析失败，exit1。
- /tmp/aos-gr-model-special.log：13 passed/6.21s/exit0；包括正式配置联合、active/model_copy拒绝。
- SDK初次实现20 passed；tsc暴露CatalogModel nullable投影不一致，单独登记后最小修复；/tmp/aos-gr-types-r2.log为空，exit0。
- /tmp/aos-gr-ui-label-red.log：1 failed/6 passed/exit1，validated错误称Eval批准；修正并补null历史渲染。
- /tmp/aos-gr-web-final.log：67 passed/3files/864ms/exit0，覆盖SDK、Catalog和Router交互。
- 累计32个后端文件 /tmp/aos-gr-regression.log 执行中，结束前不报通过。
- 一次在累计PG运行时错误启动单例复验；第二临时库迁移检测全局测试角色处于LOGIN，GUARD_POLICY_ROLE_DRIFT失败关闭（/tmp/aos-gr-model-chain-recheck.log，exit1）。未改角色检查；停止新增并行PG，在累计结束后串行复验。
- compileall与git diff --check exit0。

## BrowserPilot

已读仓库Kitewright Skill；使用原engine_adapter.BrowserPilot、独立8098临时会话，只读当前8434/aip/model-router，org-org/dev-project。不注入身份/fixture、不点击写操作。
首轮仅等body过早取到空白，第二轮只等导航词过早取到“加载中”；保留/tmp/aos-gr-browser*.png/txt。改为等真实“路由生命周期工作区”后核对，再改文案后等“已校验配置”。最终/tmp/aos-gr-browser-verified.png与txt：新文案存在、无“exact Eval批准”；已view_image核看。页面0路由/无就绪，禁止视为经营链成功；空Eval历史实际行由交互与PG测试覆盖，当前空库页面不冒充该行实测。SDK会话均已关闭。

## 剩余

真实当前库未重启/迁移/API未reload；本波不是每日重启门。没有Provider/Host/worker启动、商城源读取、旧12Run/手工run_definition、230 L0动作。真实Eval/Health来源、Review/AgentRun/首生审批/Capacity/GE held和自然经营首链仍未证明。watchdog方案未部署，Goal active。

## 最终结论

累计/tmp/aos-gr-regression.log：361 passed /8 warnings /306.28s /exit0。API目录 `.venv/bin/python -m pytest` 以下32文件加`-q`，不与专项相加：

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
- tests/aip/test_aip_model_runtime_contracts.py
- tests/aip/test_formal_model_configuration_pg.py
- tests/aip/test_aip_eval_authority_store.py
- tests/aip/test_aip_release_publication_service.py
- tests/aip/test_aip_model_runtime_resolver.py
- tests/aip/test_aip_model_runtime_api.py

累计终止后串行重验新增HTTP Eval节点断言：/tmp/aos-gr-model-chain-final.log，1 passed/6.47s/exit0。SDK初始RED1failed/19passed/525ms；最终前端67passed/864ms；最终tsc /tmp/aos-gr-types-final.log空、exit0。compileall/diff check exit0。
最终浏览器截图SHA256：942966c4f2cc3bfa62bb81c275842b86b53447549d72e246217da2ce33fd6027。当前空态只证明文案与禁入展示，没有真实运行链证据。
复审：原非空Eval合同/哈希未改；执行适配器先读取ACTIVE合同，媒体入口先要求READY，中央Eval读缺失稳定拒绝。新增合同缺失不授予运行权；角色冲突验证已在串行复验恢复，未改数据库角色门。下一波BG00GS从aip_eval_execution_authority.py及routers/evals.py评审模型/路由的正式执行与授权入口，补必要产品接线，不造通过评测。

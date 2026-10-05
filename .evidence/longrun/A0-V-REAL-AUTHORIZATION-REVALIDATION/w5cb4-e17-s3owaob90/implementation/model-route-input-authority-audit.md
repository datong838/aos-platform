# b90 原模型/路线评测输入权威核验

代码基线1578d75a；权威AOS-001343。复习产品总纲 Model routing/capacity 的 provider unknown fail-closed、完整 composition 与原 source-budget signed 入口。

- 原 aip_eval_runner.py run_by_contract 约128及 run 约216，明确拒绝 REGISTERED_MODEL/MODEL_ROUTE。原 Runner 四项隔离实测4 passed/5.90s，见 model-route-original-executor-block.log。
- 原 aip_eval_authority_store.py require_exact_passed 约519，绑定 RegisteredModelRevision/ModelRouteRevision exact candidate；LogicGraph gate不满足。
- 原 ecommerce_content_pre_review_pack.py 约137，限制 exact内容Graph，不能改成模型目标套用内容case。
- 原 test_model_eval_request_pg.py seeded_approved_model_eval_request 约253直接写Suite固定哈希与frozen合同，是隔离历史请求测试输入，不是合法正向合同生产链。
- 原 aip_model_eval_authorization.py 的preflight.execution_allowed固定false；审批不能解除执行拒绝。

原四项验证限制：实际一次性PG测试库中的独立schema、org-a/project-a等专用隔离负例，非AOS正向tenant；两个by_contract以替代Contracts对象只探拒绝。两个直接suite模式使用原注册，均在callback与Run/Report/Gate写入前拒绝。没有Provider调用，没有当前真库访问，未证明完整模型实际评测或自然经营首链。

下一行动：不再以Publication helper准备替代完整组合；回到ModelEval正式executor缺口，在原方案/Task登记完成闭环设计并实施隔离验证，然后用真实生产链产出的两个target gates组合signed八事实与三写COMMIT/API。此是局部可施工缺口，整体Goal不blocked。

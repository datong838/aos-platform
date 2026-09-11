# D03受信生成组合

基线8cc3869a，主库012，API未重载。复习现有investigation compiler/binder、CanonicalTaorRunner与AipAgentRunExecutor：调查编译/绑定已有，但未发现经营调查到AgentRunExecutor的实际worker adapter。不得另造运行/审批Owner。

新增ecommerce_analyst_growth_plan_generation.py，接收已由现有治理服务创建并处于running的D03 AgentRun及明确Decision exact、模型Budget/Capacity reservation、业务plan budget/taskType、allowed markings/max age、actor/稳定attempt id。executor由受信组合显式注入且需开启正文保留；入口仅内部服务，不接未经授权客户端字段，不创造AgentRun/绑定/审批。

1. 查询既有attempt：SUCCEEDED仅走原正文recover；任何其他已有状态拒绝（不并发抢prepared、不重发unknown）。回放前核对agentRunId、model budget/capacity/classification、attempt编号及原版本等请求绑定，actor/plan budget/task type由recover校验。并发首调由既有执行器attempt幂等/CAS拦截；不在DB事务里网络等待。
2. 首次调先检查正文表存在、当前租户D03 running run/version、exact Decision/Insight/Evidence输入；当前来源及markings核验；固定prompt构建。DB连接结束后调用既有executor.execute，沿用其预算/容量/治理/Provider/Usage/unknown协议。不得自己调用LLMAdapter绕过执行器。
3. 仅成功状态调用receiver.recover从已持久正文接收，而非依赖瞬态answer；失败/unknown不返回假计划。返回正式GrowthPlan exact引用。
4. 文件：services/aos-api/aos_api/ecommerce_analyst_growth_plan_generation.py及tests/test_ecommerce_analyst_growth_plan_generation.py。验证source/run/input/retention不就绪零调用，固定prompt绑定，一次成功接收，已成功重放无模型调用，已有unknown/prepared/invoking/failed无调用，错误attempt/run/context拒绝。

本检查点不等于worker调用点/真实首链已接；后续CanonicalTaorRunner阶段adapter及生成必要权威配置、审批当前来源重验、真实source/安装/Binding就绪仍需继续。

实现补充：aip_agent_run_executor.py增加只读retains_output_text属性，组合构造时要求显式true，避免直到调用结束才发现未保存正文。该属性不改变原默认配置或请求hash。

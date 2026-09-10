# 模型发布与路由选择治理联检验证

基线 e178b253，Task A0V-MODEL-READINESS-GOVERNANCE。新增 Owner 入口 require_model_governance，发布模型与候选选择均调用；exact price ID/revision/hash、模型/价格 tenant、ACTIVE 价格时效和当前预算开发授权联检。治理检查贯穿同一 now。非 ACTIVE 模型继续保留 staged price 编排路径。

测试先红：六项发布前校验未拒绝，第七项 Owner 入口缺失。需准确解释测试范围：发布测试截获 _publish，证明入口缺少检查；旧事务内已有哈希引用校验，不能据此宣称旧数据库可以写入任意哈希。

最终 61 passed、2 deselected、7 warnings，覆盖新 Owner 与真实 Resolver/Invoker 编排（存储及传输均为测试替身）、旧 Eval target 门、staged 配置、时钟过期。git diff --check 通过。曾误选历史 PG integration，连接 127.0.0.1:5433 refused，在 cleanup 第一个连接即退出；无数据库变更。随后明确排除该集成测试和真实无路由查询，未称数据库回归通过。原有 schema/deprecation warnings 与退出时 JDBC logger closed stream 未修改。

没有调用真实 Provider、激活 deferred DTO、写业务库或推进 authority。API 运行进程尚未重载该代码。下一步是业务结果承接 cost_pending，再完成模型/路由正式发布，之后核验真实首链与八工作台。商业金额核算继续延后，真实用量和权限边界保留。

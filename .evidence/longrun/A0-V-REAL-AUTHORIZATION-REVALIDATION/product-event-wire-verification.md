# BG-02 包wire身份边界验证

2026-09-14，基线701d01e1。发现Host递归防越权规则不允许内部测试载荷中的tenant/sourceContext身份字段，未放松规则。新增包build_event_policy_command，验证策略/Case/Dispatch/Approval引用后省略policy与Case tenant；原摘要保留。Host按可信scope恢复唯一tenant并核对原摘要，跨租户和自报tenant拒绝。

Guard新增run_policy：以精确SourceSelectionRef进入Owner原事务，在回调中由Owner draft恢复安装/generation/epoch/配置；结合真实compiled mapping和策略窗口校验，只调用Owner一次。不需要wire自报这些字段。事件服务改用六字段wire。源码Actor仍由可信Host注入，未实际装配或注册。

RED新模块缺失；累计104 passed，无skip，包括包wire原防越权守卫、Host恢复摘要、Owner单次调用、现有端口/适配器和事件服务PG。来源/方法具名替身限制仍在，不算真实业务验收。AR2新模块登记后1868模块、166分类/93迁出，全部错误数组为空；diff和memory-validate通过。

日志/tmp/product-event-wire-{red,green,final,closure,closure-final}.log。主库038/代码迁移041，未部署，Host/API/OCI未重启，无实际新Case/Run。下一波正式factory装配：查清当前真实运行身份与批准人当前权限，复用PipelineControlServiceFactory来源Owner；不得用无参旧registry的运行封印覆盖事件新语义。随后绑定与事件消费、产品入口、自然首链/八场景/观察。

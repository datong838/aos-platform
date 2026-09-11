# D03受信生成组合检查点

2026-09-11，基线8cc3869a。m1独占，不push，230 L0挂起。

- 新内部GrowthPlanGenerationService接已治理的running D03 AgentRun，先验正文表/当前来源/exact输入/版本，固定prompt构建；退出来源事务后才调用注入的现有AgentRunExecutor。
- 构造要求executor.retains_output_text为true，原executor仅新增只读属性，默认行为不变。不新建Run/绑定/审批/公开route，不直接调用LLMAdapter。
- 已有SUCCEEDED且run/version/attempt/model budget/capacity/classification/actor匹配时只recover；其他已有状态一律拒绝自动重调用。新调用非成功不创建假计划，成功再从私有原正文恢复接收。
- Red新模块不存在；Green生成/原executor49 tests通过，追加参数漂移、retention前置和真实DB成功恢复后累计176 tests passed，exit0。7既有warnings及退出日志告警不变。
- 实际DB验证采用一次性012合成图，已有成功记录走真实来源/正文/Receiver恢复，executor.execute设为不可调用以证明无重发。首次模型路径为单元替身，不是Provider实测。
- 当前缺口明确：investigation compiler/binder已有，但生产调用搜索仅router直接使用AgentRunExecutor；本service尚未由经营调查worker/stage adapter调用。不得将内部组合存在当成真实入口已接。
- 下一波：CanonicalTaorRunner阶段adapter调用与前置预算/容量/AgentRun权威配置接线；审批当前来源重验；主库012已具备正文表，API旧代码尚未重载，真实源/安装/技能Binding仍待就绪。

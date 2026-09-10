# 原批次权威完成核验

2026-09-11，基线eddd874e，A0V-EXACT-COMPLETION-20260911。

只读派生Receipt接口复用原键/hash，不调用重放。read_batch_projection_completion核验原基础水位、派生身份/stream/input_revision绑定、exact派生Receipt及每个authority_tx_id的Outbox事件数量，再统计已投影与待投影。无变化派生预期零新事件。read_saved_projection_completion从Journal读取完整准备清单，防止Dataset调用者传入不完整子集；内部Store只证明传入集合。

新增测试先失败；实现后最终Store/恢复组合49通过（SQLite真实Receipt与Outbox，Journal包装Mock）。覆盖只读回执、冲突、缺派生Receipt、未投影、完成、无关后续队列、缺Outbox、重复/无关派生命令、无变化派生零事件与包装全清单。diff-check通过。既有7警告及退出JDBC日志错误未改。

限制：尚未新接口PG验证；projected标记证明原事件已被投影，不是兼容对象当前内容不被后续更新的证明。未接Dataset持久幂等记录，也未接恢复初始保存/claim；API未重载，完整真实首链和八工作台仍未完成。不push，230 L0挂起。

下一步：Dataset结果与不可变run Receipt同事务保存并按稳定Build标识回读；然后接入实际调度恢复与真实源验证。

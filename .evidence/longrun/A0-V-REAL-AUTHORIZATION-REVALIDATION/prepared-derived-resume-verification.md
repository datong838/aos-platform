# 已准备派生命令恢复入口验证

2026-09-11，基线30ddb88a，任务A0V-PREPARED-RESUME-20260911。

新增内部resume_prepared_derived：读取不可变父/派生命令，复用当前running调度/源/图绑定锁，exact基础Receipt存在且无ignored才逐项交给原ConsistencyStore。原命令重放返回原Receipt；没有重读源、重新prepare或发布DLQ成功。绑定检查提取后旧save入口保持调用。

验证：先新增测试，模块未实现时collection失败；实现后修正测试fixture缺Payment属性、第二对象checkpoint落后两处fixture问题。最终test_ec_ingress_recovery.py + test_ecom_consistency_store.py 38通过（7新增，SQLite真实Receipt/CAS，Journal与当前绑定为mock）；已有隔离PG Journal/绑定/派生存储3通过。部分提交故障后重试结果[replayed,new]，派生Receipt总数2。基础缺失、原派生缺失、当前绑定拒绝、ignored关系均不派生提交。git diff --check通过。既有Pydantic等告警与pytest退出JDBC日志closed-file未改。

限制：无真实SSH/模型调用；未接实际executor/恢复claim，未开放HTTP，public迁移未应用，API未重载。调用者仍须提供租户事务及实际执行授权；running记录不是完整授权。未覆盖完整跨进程恢复、原始辅助输入、精确输入revision归属、投影/Dataset和真实业务首链。八工作台业务验收未完成。无push，230 L0挂起。

后续：保存规范原输入与辅助字段，打通实际初始执行和恢复claim；校准input_revision归属后，完成阶段回执/投影/Dataset接续。真实源SSH身份仍待恢复。

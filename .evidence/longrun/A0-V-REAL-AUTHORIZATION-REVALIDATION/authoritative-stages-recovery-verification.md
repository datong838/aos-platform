# 基础与派生权威阶段恢复验证

2026-09-11，基线359e1e54，任务A0V-INGRESS-RECOVER-STAGES-20260911。

新增recover_saved_authoritative_stages两连接执行：第一阶段锁scope/run、核验当前绑定、原基础命令apply、从原输入与原水位准备并保存派生；连接退出提交后第二阶段重新锁/核验、执行保存命令。已有准备不重复计算；旧缺输入且未准备的批次不写基础。resume_prepared_derived增加原水位匹配门。

先新增入口测试失败，实现后原恢复8通过。真实PG Journal/当前绑定与SQLite Store组合共12通过；再补原水位漂移、旧缺输入负例后恢复10通过，合计14独立测试。隔离PG组合注入save失败后观察：基础Receipt存在、派生命令无记录、派生Receipt为0；重试在另一个PG连接已能读到派生命令时才提交，重复调用基础/派生Receipt均仍1；meta_source停用后拒绝。diff-check通过。PG只在colima-aos-extension/aos-a0v-recovery-pg随机schema；ConsistencyStore为SQLite，不能当作全PG恢复证明。

边界：连接工厂必须成功退出提交；这是内部已授权执行原语，不是claim或HTTP权限入口。无真实上游调用，未接live executor、未将DLQ/调度标成功。投影全量完成、Dataset恢复、关联输入来源版本及完整真实首链/八工作台仍未完成。API未重载，不push，230 L0挂起。

下一步：完善实际初始执行保存和恢复调度claim装配，并处理投影/Dataset阶段；源SSH恢复仍需原可用身份。

# 派生命令准备验证

2026-09-11，基线9ecf9d5e。prepare_derived_commands返回完整命令tuple，无update；原sink通过同一生成器逐项准备提交，保持原CAS读取时序。测试JSON往返hash/版本相同及原行修改不污染准备结果。

新1项先红后绿；与OTWriter/P08组合33通过2失败。两失败是P08 executor触达默认5433投影库的OperationalError；独立进程加载git HEAD旧writer重跑P08，同样13通过及相同2失败，未改工作树。diff --check通过，既有7警告及退出closed-stream日志仍存在。

准备读取版本不构成数据库原子快照；命令仍须在真正执行时由CAS/Receipt核验。当前未持久化派生命令，也没有恢复工作器，不能以重新prepare当作旧批次恢复。API未重载，真实首链未完成。下一步将派生命令绑定原批次不可变保存并验证精确回放。不push，230 L0挂起。

# 实际durable入口已完成回读

2026-09-11，基线2aa865f2；A0V-DURABLE-COMPLETED-REPLAY-20260911。

finalizer新增only_existing内部模式；缺结果回执返回None，不调用当前完成检查、不新增Dataset。actual durable executor在输入事务退出后先查原结果，有结果直接恢复缓存并返回，跳过基础、派生和投影。completed_replay=true明确历史结果；projection本次处理数为0，历史完成记录独立completion返回。当前run/source等绑定和Journal哈希校验保持。

验证：新增执行器测试修改前1失败6通过（仍执行recover/project）；修改后15组合通过，包括4隔离PG Journal/Dataset+SQLite Store、7模拟实际入口和4运行标识专项。确认有回执无源读/无重新写入路径，无回执仍原顺序；真实PG无回执只查模式不写Dataset，已提交回读相同。git diff --check通过。不是全PG实际调度或真实源验证。

此项不允许failed/succeeded run直接越过现有running门；重新claim仍需完成。空批无变更合同、关联输入版本、真实源连接和内容异步执行仍待施工。public未迁移、API未重载，真实首链/八工作台未完成。不push，230 L0挂起。

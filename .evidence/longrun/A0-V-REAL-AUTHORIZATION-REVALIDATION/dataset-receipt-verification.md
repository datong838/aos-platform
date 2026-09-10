# Dataset不可变运行结果验证

2026-09-11，基线6841d170，A0V-DATASET-RECEIPT-20260911。

新增a0v007不可变Dataset回执，复用原run FK与FORCE RLS；提取既有Dataset Owner事务内部SQL，旧入口仍自行commit。finalize_saved_dataset核验当前绑定与原批完整投影，单事务保存Dataset/历史/运行回执，数据库提交后才发布稳定ID/时间的Build。回读旧回执不重写DB；按缓存时间防止旧run覆盖新展示。新Dataset写入用scope/RID事务锁串行，时间在获得锁后生成。

发现并修正上一轮无变化派生核验缺口：无变化Receipt需追溯同派生版本/输入hash/payload的updated=true Receipt对应有效Outbox，不能仅因本次零事件而判断完成。更新专项证明原事件未投影仍pending。

验证：先确认缺少新模块；最终Store/恢复/原Dataset单测58通过，隔离PG Journal+Dataset事务5通过，总63专项通过。PG验证a0v007空表upgrade/downgrade/upgrade、投影未完成拒绝、Receipt约束故障回滚Dataset/历史、内存发布故障后的回执恢复、稳定Build仅1、旧run不覆盖新缓存/元数据、canary无读、禁止删除及非空downgrade。PG Journal/Dataset真实事务，ConsistencyStore为SQLite，投影标记在测试中置位，不是全PG或真实上游投影验收。

扩大到旧test_ec_d1_dataset_sink_integration得到14失败1通过；在独立Python进程载入基线6841d170原data_os_store（其余生产文件未改）重跑，同样14失败1通过。首个原因OT_OUTPUT_ROW_TYPE_REQUIRED，另含旧失败降级成功预期。无reset工作树，无掩盖失败。git diff --check通过；既有告警未改。

限制：public未迁移，API未重载，新finalizer尚未接实际调度。恢复首次输入保存、claim/重启、完整真实经营首链/八工作台仍未完成；SSH仍需可用原身份。不push，230 L0挂起。下一步实际初始化/恢复调度接线以及全PG验证。

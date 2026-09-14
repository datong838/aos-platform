## 2026-09-15 SC4-5l6e6a 原生十二路许可组合

基线3aa77d274c4743e132b87ed77d0290dd229fd755，m1串行。新增test_analysis_snapshot_native_claims_pg.py，在18432实例一次性完整迁移数据库public中使用原SourceSelection/RuntimeControl/GroupClaim Owner、原meta_source版本触发器和原调度/来源外键。无替换SQL表名前缀、影子Task、临时DDL或权限扩张。actor统一fixture-host；安装资产/映射当前校验仍为明确named fixture，不是安装授权验收。原host_case提供测试安装/代次，stored最终整体回滚。

首次测试因fixture遗漏meta_pipeline父记录触发原fk_meta_schedule_pipeline_ti4d7：1 setup error/4.84s（/tmp/sc4-e6a-first.log）。按原约束补齐测试父记录，没有修改产品约束。原生四项首次通过4 passed/7.06s（/tmp/sc4-e6a-second.log）；补充断言来源触发器确实生成不同revision与第二份历史后，最终4 passed/9.91s（/tmp/sc4-e6a-final.log）。证明完整12保留和exact重放不多耗、来源版本更新及租户漂移拒绝、外层失败12组整体回滚。七项既有警告未影响断言。

AR2 phase ar2-7：1951 scanned/192 classified/93 migrated，五类错误均为空（/tmp/sc4-e6a-closure.log）。新增测试不产生反向产品依赖，无新增分类或改旧preHash。主库未迁移，未读真实源/调用模型/创建真实Task/安装发布；保留用户三份已有修改，不push，230 L0挂起。不是首链完成或跨库原子性证明。

下一波e6b：在同原生结构中建立独立提交的十二源GroupIngress准备与原投影，明确源读取替身；保留原许可先提交再读源的事务规则，不提交原stored Task事务。其后将原初始化产生的Task/Run/Checkpoint/Requirement与上述实际快照组合，删除named Pending/stage边界，再推进自然调度首链、八工作台、连续观察及发布判断。

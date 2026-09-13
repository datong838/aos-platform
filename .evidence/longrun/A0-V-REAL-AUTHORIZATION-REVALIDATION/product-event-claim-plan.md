# BG-02 修复事件已入队却永不领取

基线d9275856。控制Host前检查发现claim_next统一要求o.scheduled_at<=now，event记录scheduled_at=NULL，因此事件永远不会领取。修改services/aos-api/aos_api/automation_occurrence_store.py：明确schedule分支保留原条件，event分支要求created_at<=当前领取时间、绑定已生效且未到effective_until，之后仍共用deadline/approved/enabled/当前dispatch和runtime fence/epoch/claim gate；不放宽任何已有权限条件。

追加tests/extension_runtime/test_automation_occurrences_pg.py：真实隔离数据库新event可领取一次、租户隔离、future-created/未来生效/过期绑定/disabled/fenced/epoch漂移拒绝。保持原子attempt/key和原定时测试。测试时间取DBclock向上对齐一秒，避免当前秒小数的伪未来失败。没有启动真实dispatcher或制造真实Case/Run。

本缺陷优先于控制Host组合修复，下一波继续control Host与消费者目标承接，仍不以通用事件领取通过宣称真实经营首链完成。

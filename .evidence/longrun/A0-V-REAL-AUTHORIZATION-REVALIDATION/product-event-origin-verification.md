# 原始批次定位验证

基线34ec7f27，新增a0v_043源码。Origin与Occurrence/outbox在同外层事务落库。只有新任务能首次保存；重放保留最初run/actor；缺历史定位拒绝自动补写。读回验hash与Occurrence sourceEvent一致。

Red缺模块2失败；Green13项origin/consumer/analysis准备邻接。专用18432完整迁移临时库验证：首次来源保留、后续批次重放不覆盖、失败三者回滚、runtime更新删除truncate拒绝、negative tenant无法读取已有positive行、错误scope拒绝、历史无origin不补写。真实Source/installed仍用此前具名替身，非真实Run验收。

AR2-7 1887/169/93无错误；diff --check通过。主库仍旧版本，本波未执行主库迁移/部署/push。

下一波：平台build_event_analysis工厂；按不可变origin与当前candidate精确匹配run/actor/control，分析准备核对原origin。再接worker领取，不允许任意扫描批次承接。

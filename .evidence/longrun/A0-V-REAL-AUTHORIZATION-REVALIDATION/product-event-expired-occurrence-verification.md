# BG-02 过期事件不进入待执行队列

2026-09-14，基线0ed00d02。自然消费接线审查发现单事件及批量事件不检查冻结deadline，过期仍pending。新增两项隔离18432 PG测试RED复现；修复在已持binding锁的_insert_occurrence中读取当前DB clock，事件deadline<=now写missed。旧定时路径不改，原事件重放保持原状态/截止时间，不延长窗口、不重复outbox。

20 passed无skip，含并发去重、原子回滚、隔离、输入边界及过期混合批次；日志/tmp/event-expiry-{red,green}.log。AR2扫描1871模块、166分类/93迁出，各错误数组为空，diff通过。领取查询只选pending，因此missed不进入执行。主库/API/Host/发布包未变更。

下一波补自然消费整体接线方案与当前策略读取门：事件保存不能自动启用；启用/消费须分别有当前合同资格，沿用单写者/原Receipt/来源Owner。待补Reader内部完整性与冻结截止时间、绑定消费事务、Run承接及产品入口。真实首链、八工作台、连续观察仍未验收。

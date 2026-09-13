# BG-02 原批次候选的事务内消费回调

2026-09-14，基线e5d8767e。ProductEventCandidateReader新增run_candidates，将可信Host同步回调放在原SourceSelectionOwner内部；read继续复用返回metadata。原run/mapping校验先于回调，空观察也在Owner范围内处理；callback异常外抛，延迟结果被_reject_deferred拒绝，原Owner退出检查仍执行。无连接创建、commit、ACK或消费者注册。

RED4 failed/1 passed（缺新方法，旧read保持）；最终45 passed无skip，包含非空/空观察回调顺序、异常和延迟拒绝、原PG迟提交/原批次/租户候选及事件存储。callback测试的Owner/journal是具名替身，证明编排顺序，不证明真实来源权限；PG验证真实SQL。日志/tmp/event-callback-{red,green,final}.log。AR2扫描1871模块、166分类/93迁出各错误数组为空；diff通过。主库038/代码041，后台服务未重启，未产生真实自然Case/Run。

下一波当前策略读取与启用绑定方案：避免旧解析器处理新schema，保存/启用/消费资格分开；继续实现原来源事件metadata完整性、冻结deadline、同事务绑定消费和Run承接。整体真实首链/八场景/持续观察未完成。

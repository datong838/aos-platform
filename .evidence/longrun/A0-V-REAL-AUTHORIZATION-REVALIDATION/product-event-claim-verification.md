# BG-02 事件Occurrence可以进入领取队列

2026-09-14，基线d9275856。发现claim_next统一scheduled_at<=now导致event的NULL时间永不领取。改为schedule沿用原计划时间，event按created_at及binding有效窗口判断；共用deadline/批准/启用/dispatch和runtime围栏/epoch/claim gate保持。可领取事件只创建一次attempt/原target key。

RED正例失败；围栏测试初版构造了DB禁止的enabled+fenced状态，被约束拒绝，改为合法dispatch fence，没有放松约束。最终27 passed无skip（Occurrence PG与原纯逻辑），含事件正例、跨tenant、future-created/未来生效/过期binding/disabled/fenced/epoch、原定时与原子性回归。日志/tmp/event-claim-{red,green,final}.log。AR2扫描1876模块、166分类/93迁出各错误数组为空；diff通过。

主库038/代码042，未运行真实dispatcher、没有制造真实Case/Run。下一波回到控制Host组合及后继Run目标接线：现有通用dispatcher尚需实际生产handler绑定，不能用一次PG领取通过替代自然经营链。新operation装配/完整候选签名及独立评审/产品入口/首链/八场景/连续观察未完成。

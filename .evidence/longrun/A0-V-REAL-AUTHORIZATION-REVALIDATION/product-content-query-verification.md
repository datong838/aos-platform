# 商品内容准备固定查询验证

2026-09-11，基线6bfbdba4，AOS-000573，m1单写者。

正式MetricDefinition与QueryJob/Result通过既有Owner保存；固定计数来自精确商品Evidence读回，完整请求/输出重新计算校验，幂等Receipt不手工转写数字。保持partial与unknown freshness，不产生ready AnalystMetricValue，不绕过D01门禁。

一次性PG中新增3项测试：空完整观察与普通商品计数、重放/跨租户/源撤销（两个参数用例），零时间窗口拒绝并验证外层回滚无Query/Metric残留。商品Evidence6和QueryEvidence16回归，共25通过。最初测试失败原因是旧合成观察起止相同；仅新测试fixture记录真实正间隔，产品窗口规则不变。diff检查通过，项目记忆校验GREEN。既有7框架警告与退出JDBC日志错误仍存在，pytest退出0。

限制：真实源连接、新鲜度、质量与reconciliation仍未齐备。查询是固定观察计数，不是正式业务ready，也不是已完成首链。无主库写入、迁移、Provider调用或push。下一波复核正式事实ready所需来源/质量/对账路径，并补齐可独立实现的宿主接续。

# 当前候选验证（进行中，不是整波交付）

Rules：单m1、exact scope、最小改动、原功能与dirty保护、独立Prime只读复核。

有效HTTP反向验证：http-root-unwired-red.log，撤去8root新依赖后17fail/6pass，candidate bytes精确恢复。最初http-red.log缺factory失败；首个green日志因测试URL误写而无效，已修正真实/v1/ecommerce-workshop入口，不将那个404当安全验证。http-green-r2原辅路由误写未执行，已用实际creator contributions修复。日志全部保留。

HTTP相邻r2：49pass；延迟installed factory防止破坏legacy成功后r3：51pass。最后扩大到实际已改adapter原专项，发现额外constructor参数约束破坏installed=None的legacy成功/完整性拒绝两原用法；已删除多余约束，保留原行为。r1独立复审对应修正前版本已消费，只作历史；实际最终代码需新r2精确冻结复审，不复用r1覆盖新代码。

本轮未写业务库、未切API/Web/重启PG、未浏览器验证、未运行Provider、未重放操作。旧39Lease保留，parent完整恢复仍待后续交接边界Delivery，不以TTL清锁。8root候选不证明辅助58GET、真实读取、预算生效或经营闭环完成。

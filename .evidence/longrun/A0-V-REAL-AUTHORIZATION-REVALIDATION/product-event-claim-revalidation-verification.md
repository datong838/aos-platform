# 当前领取事务复核验证

基线1ca1c5ce。_lock_claim锁原Occurrence与attempt，锁后数据库clock_timestamp复核期限、身份、epoch、owner、幂等键。返回当前行但不提交，调用者必须维持同一写事务并继续业务授权检查。

Red：缺失方法AttributeError。Green：38项回归，其中真实18432隔离PG证明正确领取通过，错误owner/key/epoch/attempt、跨租户、租约过期、deadline到期和已accepted均拒绝。AR2-7 1883/168/93且错误数组为空；diff --check通过。

无主库/运行Host变更。尚未接正式分析调用，不把新方法存在等同生产链路完成。下一波分析准备上下文：当前policy/Case/profile、原始事件与claim，在installed命令计算前后重验，最后进入已有AnalysisAdvanceHostService。

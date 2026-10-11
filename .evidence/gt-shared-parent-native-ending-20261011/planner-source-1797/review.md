# 原固定collector规划观察

严格编译成功；admin/null拒绝，XID65551回滚/临时schema无残留。新Source完整fixture1 passed/156.67秒，原异常恢复、八节点/四证书/两审批、latewriter及实际COMMIT拒绝保留。独立回读XID65816 aborted、九表0、其他client0、profile恢复。

planner_hook在两fence内standard_planner之前观察已分析Query，只输出精确OID数字。观察64个函数，47个不在离线语法候选中，包含隐式转换、操作符、聚合和目录函数。generate_series、unnest、count还声明3个support函数；下一核pg_aggregate transition/final/combine和prosupport及真正类型/操作符依赖。缓存计划、未走分支、规划器改写/内联、native内部及生命周期仍未闭合，不能把64作为完整允许列表。测试制品不等于签名Root，未改正式库或产品，Task ACTIVE无组件Delivery。

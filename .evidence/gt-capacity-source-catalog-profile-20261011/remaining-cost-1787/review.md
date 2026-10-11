# 只读成本调查结论

完整当前FACT正文只加计时标记，r1未对齐search_path在策略表达式门拒绝；r2设置原pg_catalog后5轮原检查全部返回。两次记录均保留，无门禁删除。稳态四轮分段中位数(ms)：{"table_acl": 1.76, "global_column_acl": 3.214, "table_permission": 1.075, "public_column_acl": 4.147, "policy_loop_and_guard_lookup": 2.509}。DO解析/NOTICE和管理员invoker限制保留，不等同完整Source。

下一登记候选：同一列ACL集合的EXISTS与COUNT两次扫描是否可一次聚合保留全部非法授权与精确计数判断。先做固定SQL A/B及跨schema、PUBLIC、grant option、撤销、重复行语义矩阵，再考虑在现有catalog编译模块实现；不得改旧发布体、安装身份或减少调用。策略环路约2.5ms，暂不优先改签名规范化。完整Source/collector到期仍未解决，没有Delivery。

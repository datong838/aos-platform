# 内存受限时的原库只读对账

Rules：沿231、parent恢复Task和单写Lease；先方案后本目录 bounded_readonly_fingerprint.py；不改产品代码、原库权限/数据或服务，不重启、不新增容器。候选 A 为原650表对账方式内存收敛，依赖同一权威卷和原只读维护授权；候选 B 为已登记Source reader/锁兼容分析。选择 A，先解决可安全验证原库完整性的实际问题。

此前 helper 把650表哈希聚合拼成单一UNION查询，资源不足时当前库只读连接中断；未证明由此唯一造成OOM。本轮保留同一 row_to_jsonb→sha256→排序string_agg→sha256 指纹算法，只把650个聚合拆成同一个 REPEATABLE READ READ ONLY 事务中的逐表语句，work_mem1MB、禁并行、statement_timeout5s。查询每条只输出表名、count、hash，不输出原始行、口令或源码外部数据；严格ON_ERROR_STOP，失败即整次无完整结论，不复用部分结果当650表通过。

先只读核定原容器ID/卷/cluster/schema、schema表数量及MemAvailable，要求至少256MiB可用，未满足不运行。通过后单次有界对账，完整输出恰650唯一表；所有文件O_EXCL写新证据，不覆盖历史。记录当前快照，不宣称与演练前历史指纹相同（前波未保存完整对应baseline）；对比只有另一个合法已保存同实例baseline存在才进行。此次read-only事务不申请或执行安装/Host任何效果。后续完整恢复演练仍须充足容量、完整native restore terminal及独立验收，不把本对账当该演练通过。

# D01 查询结果与受控证据绑定方案

2026-09-11，基线 b23dcb08，m1，AOS-000573。复核技术15（指标最小合同、同一冻结cutoff、unknown不等于0）与既有D01输入方案。用户已授权连续串行开发。

## 本波范围与文件

新增 `services/aos-api/aos_api/ecommerce_analyst_portrait_query_sources.py`：显式同连接，先经现有 read_analysis_bundle 获取同Task全量L3获准原文，再读取唯一Query Owner的 exact result 和原始 MetricQueryRequest。只接受完整、fresh、当前cutoff相同的结果；请求必须绑定指定指标定义版本及显式窗口。要求获准Evidence payload携带完整 `queryResult`、`queryRequest` 与 `metricDefinitionRef`，逐字节规范JSON对比正式查询结果，不接受仅有引用的证据。检查source和column markings没有降级到payload标记之外。

新增 `services/aos-api/tests/test_ecommerce_analyst_portrait_query_sources.py`：缺失/错指标/错窗口/旧cutoff/partial/empty/内容漂移/源过期/降级标记/跨租户/仅引用拒绝，同连接测试和隔离PostgreSQL正式Query Owner验证。接口返回原查询请求、结果与获准原文，不派生数值、不输出页面ready或Insight。

## 边界与后续

不修改公共Query哈希算法，不新增第二指标事实表。指标定义的当前性由上一波 read_portrait_authorities 在同事务核验；本函数核验对应查询版本，不能单独代表完整画像输入ready。查询源freshness检查与最大年龄检查都执行。无Provider/新路由/主库迁移。Evidence的正式自动生产及完整业务指标最小合同仍是下一波，不允许手工填Evidence作为真实业务验收。快照字段协议仅供正式生产者使用，不将caller提供的dict当授权。失败不返回任何查询正文，不记录敏感值。

退出：针对性拒绝测试、现有受控读取回归、隔离库验证、方案一致性审查、证据、精确文件提交。下一波补正式查询证据生产、画像生成接续；真实SSH源仍未恢复，不重复未变化认证。不push，230 L0挂起。

审查补充：原请求中的filters/selection也可能敏感；要求获准正文同时保留完整queryRequest并规范JSON一致，不因查询结果获准而额外返回未披露请求。metricDefinitionRef规范JSON比较避免bool与integer相等的语言级歧义。

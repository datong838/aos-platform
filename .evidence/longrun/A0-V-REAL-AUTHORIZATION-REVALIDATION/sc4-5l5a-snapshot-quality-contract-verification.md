# SC4-5l5a 验证

基线15990e6a；m1串行；不push；230 L0挂起。

### SC4-5l5a 显式完整快照质量合同

新增SnapshotQueryQualityMeasurement，schema aos.data-requirement-snapshot-query-quality-measurement/v1。严格一个完整组Evidence（id/hash一致、整数revision1、无receipt_id）和精确QueryResultRevision；旧两个variant字段不变。原evaluate_quality与QualityEvidenceInput判别器直接兼容，不复制评分器，不修改threshold/原请求。DTO只保证结构，不认证来源；l5b须原Owner当前验证和查询逐项重算。

Red缺新增类型；新合同与原质量/存证51 passed/15.17秒，旧CanonicalQueryMeasurement额外8 passed/5.19秒，共59。错误来源/重复/空引用/string revision/receipt/query类型、空分母与低质量并存、源年龄不被query时间刷新、原QualityEvidenceInput往返均验证。AR2扫描1937/188/93五类错误空，memory validate GREEN。无PG/源/模型/主环境动作。

下一波SC4-5l5b：原source Evidence当前Owner内读取固定QueryResult，原requirement完整hash/策略与逐类counts构造新测量；实际Shop唯一范围人口（不跨类型相加）、read_started_at保守freshness、原QualityEvidenceStore存证与消费时当前复核。历史已存证不作为永久许可；原Fulfillment预期转换仍l6。真实主环境12类型892行、主安装升级、真实首链与八场景仍待执行。

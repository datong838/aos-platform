# D01 精确查询与获准原文绑定验证

2026-09-11，m1，基线b23dcb08，AOS-000573。新增内部read_portrait_metric_query；先完整同Task L3披露，再复用正式Query Owner核验精确result及原MetricQueryRequest，要求same frozen cutoff/window、指定MetricDefinition版本、succeeded当前结果、complete且source fresh/未超龄。完整queryRequest/queryResult/metricDefinitionRef必须在同一获准Evidence原文中，规范JSON一致；source/column markings不可降级。未新增第二指标权威，未改原公共Query行为。

## 新鲜验证

先写拒绝测试，模块不存在时收集失败；实现后最终27项专项（含1组完整一次性PG）。累计163项通过：portrait_query_sources、portrait_sources、analysis_sources、diagnosis_generation、diagnosis_receiver、diagnosis_service；7条既有Pydantic/Starlette警告，退出码0，结束时既有JDBC关闭日志流错误不影响结果。

PG验证通过真实Query Owner创建、启动、保存合成计数查询，然后由正式Production Owner建立Bundle和L3披露；真实读取得到原结果，Evidence撤销后拒绝。任务/查询Owner实际执行，Evidence/Brief仍为隔离夹具SQL，不是正式生产器、真实源或业务闭环证据。主库无业务写入、无迁移、无Provider、无API重载。

## 审查与剩余

请求filters/selection也可能敏感，已要求完整请求同时获准；metric ref规范JSON比较拒绝bool伪装revision。当前Metric/Method/Eval仍须由上一波同事务reader检查，本函数不可独立宣布指标ready。尚缺完整业务指标合同、自动Evidence生产、D01生成/工作者、三阶段宿主及实际配置。真实源恢复记录仍是SSH认证拒绝，未重复连接。真实首链、八场景和连续观察未完成；测试数不能换算业务百分比。不push，230 L0挂起。

下一波：正式查询证据生产与幂等引用，继续D01画像链；保留来源授权、单写者、隔离、原截止时间和未知不得猜测规则。
